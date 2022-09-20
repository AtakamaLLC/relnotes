DELETE_ON_ERROR:

env:
	python -mvirtualenv env

requirements:
	python -mpip install -r requirements.txt

lint:
	python -m pylint relnotes
	black relnotes
	PYTHONPATH=. python relnotes/main.py --lint

note:
	PYTHONPATH=. python relnotes/main.py --create

black:
	black relnotes tests

test:
	PYTHONPATH=. pytest --cov relnotes -v tests

publish:
	rm -rf dist
	python3 setup.py bdist_wheel
	twine upload dist/*

install-hooks:
	pre-commit install


.PHONY: docs black publish env requirements
