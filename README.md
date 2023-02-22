# cloudflare-ddns-updater-service
Python script to run as a service in your server. It automatically updates the ip record for your domain names.
## How it works
Just create a file named cloudflare-ddns-updater.ini or let the program create it when it doesn't exist. Then fill the entries:
- ZoneIdentifier: a code that represents one of your domains. It can be found by clicking on one of your websites and looking on the main page.
- ApiToken: cloudflare's api token with permissions Zone Settings:Read, Zone:Read, DNS:Edit.
- DNSRecordName: the name entry on the dns record. For ipv4s it is the website's domain.
- DNSRecordType: the type of record to update. Can be "A" for ipv4, "AAAA" for ipv6.
- SecondsToSleepWhenFail: how many seconds to sleep when something goes wrong in the update loop. Default: 5
- SecondsToSleepWhenSuccess: how many seconds to sleep when the record is updated or doesn't need the update. Default: 30
- DebugMode: True if you want the log file to be filled with debug informations (gets big faster). Default: False

Example:
```ini
[CONFIGURATION]
DebugMode = False
;update the A record for example.com in zone_identifier
[zone_identifier_here]
ApiToken = token_here
DNSRecordName = example.com
DNSRecordType = A
SecondsToSleepWhenFail = 5
SecondsToSleepWhenSuccess = 30
;update the AAAA record for example.com in zone_identifier
[zone_identifier_here]
ApiToken = token_here
DNSRecordName = example.com
DNSRecordType = AAAA
SecondsToSleepWhenFail = 10
SecondsToSleepWhenSuccess = 60
;update the A record for example.org in a different zone_identifier
[other_zone_identifier_here]
ApiToken = token_here
DNSRecordName = example.org
DNSRecordType = A
SecondsToSleepWhenFail = 20
SecondsToSleepWhenSuccess = 120
```
## Using systemctl
Example configuration cloudflare-ddns-updater.service:
```ini
[Unit]
Description=Cloudflare DNS Record Updater
After=network.target
StartLimitIntervalSec=0
[Service]
Type=simple
Restart=on-failure
User=username
WorkingDirectory=/path/to/
ExecStart=/usr/bin/python3 /path/to/cloudflare_ddns_updater.py

[Install]
WantedBy=multi-user.target
```
