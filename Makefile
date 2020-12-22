VENV=. venv/bin/activate

FLASK_FLAGS=FLASK_APP=psan FLASK_RUN_HOST=0.0.0.0
POT_HOME=psan/translations
FLAKE_BIN=venv/bin/flake8

# Python venv environment
$(VENV): requirements.txt
	test -d venv || python3 -m venv venv
	$(VENV); pip install -Ur requirements.txt
	touch venv/bin/activate

$(FLAKE_BIN): $(VENV)
	$(VENV); pip install flake8
	touch $(FLAKE_BIN)

venv: $(VENV)

venv-debug: $(VENV) $(FLAKE_BIN)

# Translations
# Extract strings for translation
$(POT_HOME)/base.pot: babel.cfg $(shell find . -name "*.py" -o -name "*.html") venv
	test -d $(POT_HOME) || mkdir $(POT_HOME)
	$(VENV); pybabel extract -F babel.cfg -k lazy_gettext -o $(POT_HOME)/base.pot .

# Create or update Czech translation
$(POT_HOME)/cs/LC_MESSAGES/messages.po: $(POT_HOME)/base.pot venv
	test -d $(POT_HOME)/cs || ($(VENV); pybabel init -i $(POT_HOME)/base.pot -d $(POT_HOME) -l cs)
	test -d $(POT_HOME)/cs && ($(VENV); pybabel update -i $(POT_HOME)/base.pot -d $(POT_HOME))

# Compile translation
%.mo: %.po
	$(VENV); pybabel compile -d $(POT_HOME)

translate: $(POT_HOME)/cs/LC_MESSAGES/messages.mo

# Build
instance:
	mkdir instance

build: venv instance

# Run web
run: build worker
	$(VENV); $(FLASK_FLAGS) flask run

worker: build
	($(VENV); $(FLASK_FLAGS) celery -A psan.celery worker)&

# Docker
docker-debug: instance
	echo "COMMIT_REV= \"bind-mount\""  > ./instance/config.py
	docker-compose -f docker-compose.yaml -f docker-compose.debug.yaml up

docker-build: instance translate
	echo "COMMIT_REV= \"$(shell git rev-parse HEAD)\""  > ./instance/config.py
	docker-compose build

docker-clean:
	docker-compose down -v

# Debug
lint: $(FLAKE_BIN)
	$(VENV); flake8 . --exclude=venv,__pycache__ --count --select=E9,F63,F7,F82,H306,H301 --show-source --statistics
	$(VENV); flake8 . --exclude=venv,__pycache__ --count --exit-zero --max-complexity=10 --max-line-length=120 --statistics

# Standard staff
clean: docker-clean
	rm -r venv
	rm -r instance

.PHONY: venv, venv-debug, run, build, docker-debug, docker-build, docker-clean, lint, clean
