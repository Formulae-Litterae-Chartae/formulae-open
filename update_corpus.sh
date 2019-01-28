#!/bin/bash
# stop server
supervisorctl stop formulae-nemo

# rebuild search index
source /home/ubuntu/env/bin/activate
python rebuild_elasticsearch.py

# rebuild cache
python /home/ubuntu/formulae-capitains-nemo/manager.py flush_resolver
python /home/ubuntu/formulae-capitains-nemo/manager.py parse

# restart server
supervisorctl start formulae-nemo
