# Copy of https://gist.githubusercontent.com/holyjak/b5613c50f37865f0e3953b93c39bd61a/raw/32f153b2c1764b4e967a8e8b88f03a014212e777/s3_multipart_upload.py
# with some minor modifications
import os
import boto3
import logging

class S3MultipartUpload(object):
  # AWS throws EntityTooSmall error for parts smaller than 5 MB
  PART_MINIMUM = int(5e6)

  def __init__(self,
               bucket,
               key,
               local_path,
               part_size=int(15e6),
               profile_name=None,
               region_name="eu-west-1",
               verbose=False):
    self.bucket = bucket
    self.key = key
    self.path = local_path
    self.total_bytes = os.stat(local_path).st_size
    self.part_bytes = part_size
    assert part_size > self.PART_MINIMUM
    assert (self.total_bytes % part_size == 0
            or self.total_bytes % part_size > self.PART_MINIMUM)
    self.s3 = boto3.session.Session(
        profile_name=profile_name, region_name=region_name).client("s3")
    if verbose:
      boto3.set_stream_logger(name="botocore")

  def abort_all(self):
    mpus = self.s3.list_multipart_uploads(Bucket=self.bucket) # Prefix=key
    aborted = []
    logging.info("Aborting", len(mpus), "uploads")
    if "Uploads" in mpus:
      for u in mpus["Uploads"]:
        upload_id = u["UploadId"] # also: Key
        aborted.append(
            self.s3.abort_multipart_upload(
                Bucket=self.bucket, Key=self.key, UploadId=upload_id))
    return aborted

  def get_uploaded_parts(self, upload_id):
      parts = []
      res = self.s3.list_parts(Bucket=self.bucket, Key=self.key, UploadId=upload_id)
      if "Parts" in res:
          for p in res["Parts"]:
              parts.append(p) # PartNumber, ETag, Size [bytes], ...
      return parts

  def create(self):
    mpu = self.s3.create_multipart_upload(Bucket=self.bucket, Key=self.key)
    mpu_id = mpu["UploadId"]
    return mpu_id

  def upload(self, mpu_id, parts = []):
    uploaded_bytes = 0
    with open(self.path, "rb") as f:
      i = 1
      while True:
        data = f.read(self.part_bytes)
        if not len(data):
          break

        if len(parts) >= i:
            # Already uploaded, go to the next one
            part = parts[i - 1]
            if len(data) != part["Size"]:
                raise Exception("Size mismatch: local " + str(len(data)) + ", remote: " + part["Size"])
            parts[i - 1] = {k: part[k] for k in ('PartNumber', 'ETag')}
        else:
            part = self.s3.upload_part(
                # We could include `ContentMD5='hash'` to discover if data has been corrupted upon transfer
                Body=data, Bucket=self.bucket, Key=self.key, UploadId=mpu_id, PartNumber=i)
            parts.append({"PartNumber": i, "ETag": part["ETag"]})

        uploaded_bytes += len(data)
        logging.info("{0} of {1} bytes uploaded ({2:.3f}%)".format(
            uploaded_bytes, self.total_bytes,
            as_percent(uploaded_bytes, self.total_bytes)))
        i += 1
    return parts

  def complete(self, mpu_id, parts):
    #print("complete: parts=" + str(parts))
    result = self.s3.complete_multipart_upload(
        Bucket=self.bucket,
        Key=self.key,
        UploadId=mpu_id,
        MultipartUpload={"Parts": parts})
    return result


# Helper
def as_percent(num, denom):
  return float(num) / float(denom) * 100.0

def multi_part_upload(bucket, key, path, profile_name=None, region_name="eu-west-1", uploadid=None):
  mpu = S3MultipartUpload(
      bucket,
      key,
      path,
      profile_name=profile_name,
      region_name=region_name)

  if  uploadid != None:
      mpu_id = uploadid
      logging.info("Continuing upload with id=", mpu_id)
      finished_parts = mpu.get_uploaded_parts(mpu_id)
      parts = mpu.upload(mpu_id, finished_parts)
  else:
      # abort all multipart uploads for this bucket (optional, for starting over)
      mpu.abort_all()
      # create new multipart upload
      mpu_id = mpu.create()
      logging.info("Starting upload with id=", mpu_id)
      # upload parts
      parts = mpu.upload(mpu_id)

  # complete multipart upload
  logging.info(mpu.complete(mpu_id, parts))
