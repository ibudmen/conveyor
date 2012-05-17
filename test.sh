#! /bin/sh

# set -x

_modules='
	conveyor
	conveyor.client
	conveyor.client.__main__
	conveyor.debug
	conveyor.enum
	conveyor.event
	conveyor.ipc
	conveyor.jsonrpc
	conveyor.log
	conveyor.main
	conveyor.process
	conveyor.recipe
	conveyor.server
	conveyor.server.__main__
	conveyor.task
	conveyor.thing
	conveyor.toolpath
	conveyor.toolpath.skeinforge
	conveyor.visitor
'

if [ ! -d obj/ ]
then
	mkdir obj/
fi

env PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=src/main/python/ coverage run --branch test.py -- -v ${_modules}
_code=$?
env PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=src/main/python/ coverage annotate -d obj/ --include 'src/main/python/*'
env PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=src/main/python/ coverage html -d obj/ --include 'src/main/python/*'
env PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=src/main/python/ coverage xml -o obj/coverage.xml --include 'src/main/python/*'
env PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=src/main/python/ coverage report --include 'src/main/python/*'
exit ${_code}
