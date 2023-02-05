import os

for i in range(1):
    with open(f"backup/test{i}.tar.gz.gpg", "w") as f:
        f.write("test")
    with open(f"backup/test{i}.tar.gz.gpg", "w") as f:
        f.writelines('range(10)')
        f.writelines('range(10)')

    