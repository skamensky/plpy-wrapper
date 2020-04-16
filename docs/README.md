You can install the dependencies for building the documentation with the following command

```
pip install plpy-wrapper[docs]
```

However being that the docs aren't included in the pypi package you'll need to clone this github repository to actually build the documentation.

Once you've cloned the repo and installed the dependencies, switch to the `docs` directory and run 

```
make html
```

This will output an `index.html` file in the `build\html` directory. Open that file to browse the documentation you've just built!