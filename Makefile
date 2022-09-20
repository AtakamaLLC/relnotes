DELETE_ON_ERROR:

env:
	python -mvirtualenv env

requirements:
	python -mpip install -r requirements.txt

lint:
	python -m pylint rnotes
	black rnotes
	PYTHONPATH=. python rnotes/main.py --lint

note:
	PYTHONPATH=. python rnotes/main.py --create

black:
	black rnotes tests

test:
	PYTHONPATH=. pytest --cov rnotes -v tests

publish:
	rm -rf dist
	python3 setup.py bdist_wheel
	twine upload dist/*

install-hooks:
	pre-commit install


.PHONY: docs black publish env requirements
