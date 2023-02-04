import os
import old.upload_backup as upload_backup
# Python script to upload newest backup to AWS Glacier
# This script is intended to be run from cron
# It will upload the newest backup to AWS Glacier

# Set the path to the backup directory
BACKUP_DIR=""

# Set default arguments for glacier
VAULT_NAME=""
REGION=""
NUM_THREADS="10"

if __name__ == "__main__":
    # Get the newest backup
    newest_backup = max([os.path.join(BACKUP_DIR, f) for f in os.listdir(BACKUP_DIR) if f.endswith(".tar.gz.gpg")], key=os.path.getctime)
    # Upload the newest backup
    print(newest_backup)
    ids = newest_backup.split("/")[-1].split("-")[0:2]
    ids.insert(1, "-")
    upload_id = "".join(ids)
    print(os.path.join(BACKUP_DIR, "uploaded.txt"))
    with open("/home/pi/uploaded.txt", 'r') as f:
        for line in f:
            if line.replace('\n', '') == upload_id:
                print("File already uploaded \n exiting...")
                exit(0)
 
    with open("/home/pi/uploaded.txt", 'a') as f:
        f.write(upload_id + '\n')
    print("Upload...")
    upload_backup.upload(vault_name=VAULT_NAME, file_name=newest_backup, region=REGION, arc_desc='', part_size=8, num_threads=NUM_THREADS, upload_id=upload_id)
