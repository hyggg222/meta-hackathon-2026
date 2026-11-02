# Deploy: one small EC2 instance behind CloudFront

Why: Messenger needs a public HTTPS address that stays up. CloudFront gives a free `https://dxxxx.cloudfront.net` address with a valid certificate (no domain needed) and forwards to the instance over HTTP. The instance runs the image built from the `Dockerfile` in the repo root.

Everything below is done by the project owner; no cloud resource is created by an agent. Region: Ireland (`eu-west-1`), the closest to the deadline's time zone.

## 1. Launch the instance (about 10 minutes)
1. EC2, Launch instance. Name `shrimp`. AMI: Ubuntu Server 22.04 LTS. Type: `t3.small` (2 GB RAM; OpenCV and the Node decoder need room). Storage: 20 GB.
2. Key pair: create one and keep the `.pem` file (never commit it).
3. Security group, inbound rules:
   - SSH (22) from "My IP".
   - HTTP (80) from the CloudFront managed prefix list `com.amazonaws.global.cloudfront.origin-facing` (so only CloudFront reaches the app).
4. Launch. Note the **Public DNS name** of the instance (`ec2-...eu-west-1.compute.amazonaws.com`).

## 2. Install Docker and copy the app (about 10 minutes)
On the instance (`ssh -i key.pem ubuntu@<public DNS>`):
```
sudo apt-get update && sudo apt-get install -y docker.io
sudo usermod -aG docker ubuntu   # then log out and in again
```
From the laptop, send the code (tracked files only, so no `.env`, no photos):
```
git -C /home/huy/meta-hack-2026-worktrees/shrimp-killtest archive --format=tar HEAD | ssh -i key.pem ubuntu@<public DNS> 'mkdir -p app && tar -x -C app'
scp -i key.pem /home/huy/meta-hack-2026-worktrees/shrimp-killtest/.env ubuntu@<public DNS>:app/.env
```
Then on the instance:
```
cd app && docker build -t shrimp .
sudo mkdir -p /srv/shrimp-data && sudo chown ubuntu /srv/shrimp-data
docker run -d --name shrimp --restart unless-stopped --env-file .env -v /srv/shrimp-data:/app/data -p 80:8000 shrimp
curl -s localhost/api/dashboard | head -c 200
```
`.env` keeps the same settings as on the laptop (`META_API_KEY`, `MESSENGER_*`, `SPARK_REPLIES=1`). The SAM cache and the database live in `/srv/shrimp-data` and survive a restart of the container.

## 3. CloudFront (about 10 minutes)
1. CloudFront, Create distribution. Origin domain: the instance's public DNS name. Protocol: HTTP only, port 80.
2. Default cache behaviour: Viewer protocol policy "Redirect HTTP to HTTPS"; Allowed methods "GET, HEAD, OPTIONS, PUT, POST, PATCH, DELETE"; Cache policy `CachingDisabled`; Origin request policy `AllViewer` (this forwards the `X-Hub-Signature-256` header and the query string the webhook needs).
3. Create. Wait until the status is Deployed (a few minutes). Note the domain `dxxxx.cloudfront.net`.
4. Check: `curl -s https://dxxxx.cloudfront.net/api/dashboard | head -c 200`.

## 4. Point Messenger at it (about 5 minutes)
1. In the Meta app, Messenger API settings, Webhooks: callback URL `https://dxxxx.cloudfront.net/webhook/messenger`, the same verify token, Verify and save. The `messages` field stays ticked for the Page.
2. On the instance, set `DASHBOARD_URL=https://dxxxx.cloudfront.net` in `app/.env` and run `docker restart shrimp`.
3. Message the Page: send "tình hình", then a tray photo.

## Update after a code change
Repeat the `git archive` and `docker build`, then `docker rm -f shrimp` and the `docker run` line.

## Risks
- Messenger photo download and SAM take 5 to 15 seconds; CloudFront waits up to 30 seconds by default for the origin, enough for the webhook because it answers 200 at once and works in the background.
- While the Meta app is in development mode only app admins, developers and testers can talk to the bot.
- The dashboard page is public to anyone with the CloudFront address, with demo data and the farmer's feed entries. Do not share the address outside the demo.
- Stop the instance and delete the distribution after the judging if it is no longer needed.
