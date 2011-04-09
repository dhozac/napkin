PYTHON = python

%:
	$(PYTHON) setup.py $@
clean:
	rm -fr MANIFEST build dist
