FROM gcc:9
WORKDIR /build

COPY bin/generate-makefile \
    patch/issue1706863/fix_sqlite3_setup_error.patch \
    ./
RUN ./generate-makefile >Makefile && \
    make download_all && \
    make build_all && \
    make install_all && \
    make clean_all

COPY bin/all-python.py /opt/all-python.py
RUN \
	cd /usr/local/bin && \
	echo '#!/bin/sh' >all-python && \
	echo 'exec /opt/all-python/Python-3.7.5/bin/python /opt/all-python.py "\$@"' >>all-python && \
	chmod +x all-python
ENTRYPOINT ["/usr/local/bin/all-python"]
