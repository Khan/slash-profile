PROJECT="slack-profile"

serve:
	dev_appserver.py --port 8090 --admin_port 8010 app.yaml

deploy:
	[ -f "secrets.py" ] || ( echo "Please create a secrets.py file with\n\tslack_bot_token = 'xoxb-...'\n\ttoken = '...'\nin it." ; exit 1 )
	gcloud app deploy app.yaml --promote --stop-previous-version --project $(PROJECT)

.PHONY: serve deploy
