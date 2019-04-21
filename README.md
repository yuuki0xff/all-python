# all-python
The all-python is a helper script to build python interpreter and run some code on various python versions.
Supports historical CPython versions since v2.0.1.


## Installation
Download the pre-built docker image from docker hub.

```bash
$ docker pull yuuki0xff/all-python
```

If you want to build the docker image yourself, please run the following command.
It takes few hours and 30GB+ free space on local storage to build.

```bash
$ make
```


## Usage
Show help:

```bash
$ docker run --rm -it yuuki0xff/all-python --help
```

Run a small script on all python versions:

```bash
$ docker run --rm -it yuuki0xff/all-python -- -c 'print(type(u""))'
=====> 2.0.1 ~ 2.7.16 <=====
<type 'unicode'>
=====> 3.0 ~ 3.2.6 <=====
  File "<string>", line 1
    print(type(u""))
                 ^
SyntaxError: invalid syntax
=====> 3.3.0 ~ 3.7.3 <=====
<class 'str'>
```


Run a small script on python 2.7.x:

```bash
$ docker run --rm -it yuuki0xff/all-python -v 2.7.x -- -c 'print(type(u""))'
=====> 2.7.1 ~ 2.7.16 <=====
<type 'unicode'>
```


Run the unit test of [flask framework](http://flask.pocoo.org/) on all python versions:

```bash
$ docker run --rm -it yuuki0xff/all-python \
	--before 'git clone https://github.com/pallets/flask &>/dev/null' \
	--exec 'cd flask && make test'
```

Enter interactive shell:

```bash
$ docker run --rm -it yuuki0xff/all-python bash
```


## Related projects
* [akr/all-ruby](https://github.com/akr/all-ruby) - Run various versions of ruby command.

