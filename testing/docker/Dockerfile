FROM postgres:12

RUN apt-get update 
RUN apt-get -y install python3 postgresql-plpython3-12 python3-pip nano
RUN pip3 install coverage plpy-wrapper

ENTRYPOINT ["/docker-entrypoint.sh"]

EXPOSE 5432
CMD ["postgres"]

#so we don't run into race conditions with the DB not being ready
HEALTHCHECK --interval=100ms --retries=40 CMD /usr/lib/postgresql/12/bin/pg_isready