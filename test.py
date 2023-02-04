import os

for i in range(10):
    with open(f"backup/test{i}.tar.gz.gpg", "w") as f:
        f.write("test")
    with open(f"test{i}.tar.gz", "w") as f:
        f.write("backup/test")
    