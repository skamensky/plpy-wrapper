from setuptools import setup

setup(
    name="plpy-wrapper",
    version="0.1",
    packages=["plpy_wrapper"],
    python_requires=">=3.7, <=3.8",
    extras_require={
        "docs": [
            "sphinx",
            "sphinxcontrib-napoleon",
            "sphinx-autodoc-typehints",
            "sphinx_rtd_theme",
        ],
        "pypipublish": ["wheel"],
    },
    license="MIT",
    long_description=open("README.md").read(),
    long_description_content_type="text/markdown",
    url="https://github.com/skamensky/plpy-wrapper/",
    author="Shmuel Kamensky",
    keywords="postgres plpython plpy wrapper",
)
