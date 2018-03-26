# Tornad pub-sub app using tcp server

### test response on correct message:
```bash
python -m unittest discover test
```
### launch:
```bash
pip install -r requirements.txt
virtualenv -p python3  venv
source venv/bin/activate
python tornado_server.py
```

### test manually: 
```bash
python manual_test.py
python manual_test.py
python manual_test_notify.py
```