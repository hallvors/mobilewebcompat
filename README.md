# mobilewebcompat

The code that runs [arewecompatibleyet.com](http://arewecompatibleyet.com)

## Contributing

1. Clone this repository
2. Install the python requirements specified in requirements.txt with:
```bash
pip install -r requirements.txt
```

3. Start the server with:
```bash
python wsgi.py
```

4. Open http://localhost:8000 in your browser

5. To update the local cache of bug data, run ``python preproc/buildlists.py`` (this will take a while).

## Deployment

The arewecompatibleyet.com site is hosted on Heroku. Someone with sufficient permissions can update it by adding a named remote to git:

```
heroku  https://git.heroku.com/arewecompatibleyet.git (fetch)
heroku  https://git.heroku.com/arewecompatibleyet.git (push)
```

and use ``git push heroku master`` to update the live instance.
## License

[Mozilla Public License, ver. 2](https://www.mozilla.org/MPL/2.0/)
