DELETE_ON_ERROR:

env:
	python -mvirtualenv env

requirements:
	python -mpip install -r requirements.txt

lint:
	python -m pylint relnotes
	black relnotes

docs:
	PYTHONPATH=. docmd relnotes -u https://github.com/atakamallc/relnotes/blob/master/relnotes > README.md

black:
	black relnotes tests

test:
	pytest --cov relnotes -v tests

publish:
	rm -rf dist
	python3 setup.py bdist_wheel
	twine upload dist/*

install-hooks:
	pre-commit install


.PHONY: docs black publish env requirements
