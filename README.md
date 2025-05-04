## Setup:

I have all my apps (nextcloud, maria-db and redis) running in docker
thus I use the docker prepend for creation of the DB backup

Files in this repo are owned by root and copied to
`/etc/cloud_backup`
and scripts are run by !root! using crontab
