.PHONY: setup build verify serve test clean

setup:            ## build the database and the app, then verify everything
	python3 build/gen_db.py
	python3 build/verify.py
	python3 build/build_app.py

build:            ## rebuild app/index.html only
	python3 build/build_app.py

verify:           ## run the content gate on its own
	python3 build/verify.py

serve:            ## local run, password from .env or the shell
	APP_PASSWORD=$${APP_PASSWORD:-localdev} python3 app/server.py

test:             ## end to end: auth, gzip, rate limit
	bash tests/smoke.sh

clean:
	rm -f data/mock.db app/index.html app/index.html.gz
	find . -name __pycache__ -type d -exec rm -rf {} +
