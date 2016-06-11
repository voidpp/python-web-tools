
from setuptools import setup, find_packages

setup(
    name = "voidpp-web-tools",
    desciption = "various web related python tools",
    version = "1.0.0",
    author = 'Lajos Santa',
    author_email = 'santa.lajos@coldline.hu',
    url = 'https://github.com/voidpp/python-web-tools.git',
    install_requires = [
        "voidpp-tools==1.5.4",
        "json-rpc==1.10.3",
        "Werkzeug==0.11.5",
        "requests==2.9.1",
    ],

    packages = find_packages(),
)
