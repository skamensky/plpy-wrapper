set docker_dir=%cd%
cd ..
set test_package_dir=%cd%
cd %docker_dir%

SET image_name=plpy-wrapper-testenv-image
SET container_name=plpy-wrapper-testenv-container
SET container_docker_dir=/mnt/docker_dir
SET container_test_package_dir=/mnt/test_package
SET coverage_file=coverage_results.xml
SET volume_name=plpy-wrapper-testenv-volume

docker build -t %image_name% . 

docker volume create --name %volume_name%

docker run ^
    --detach ^
    --env POSTGRES_HOST_AUTH_METHOD=trust ^
    --env PGDATA=/usr/var/postgres/data ^
    --env DOCKER_DIR_FROM_HOST=%container_docker_dir% ^
    --env TEST_PACKAGE_DIR_FROM_HOST=%container_test_package_dir% ^
    --env PYTHONPATH=%container_test_package_dir% ^
    --publish 54320:5432 ^
    --name %container_name% ^
    --tty ^
    --volume "%docker_dir%":%container_docker_dir% ^
    --volume %volume_name%:/usr/var/postgres/data ^
    --volume %test_package_dir%:%container_test_package_dir% ^
    %image_name%


@REM if you want to debug the data on the host system you can export the data by uncommenting the line below
@REM docker run --rm --volumes-from %container_name% -v %docker_dir%/data:/backup ubuntu tar cvf /backup/backup.tar /usr/var/postgres/data



@REM due to race conditions, sometimes the tests can be run before the setup has complete (when the DB starts in between the two commands)
@REM therefore we use a python script to wait until the DB has started up
@REM see https://github.com/moby/moby/issues/16754#issuecomment-145388645
python %docker_dir%\wait_until_container_is_running.py %container_name%

docker exec %container_name% psql -U postgres -f /mnt/docker_dir/setup_db.sql
@REM for some reason info output of postgres is considered stderr so we redirect stderr to stdout, we output the coverage results to a file on the host
docker exec %container_name% psql -U postgres -f /mnt/docker_dir/run_tests.sql 1> %coverage_file% 2>&1
@REM captures up until the test coverage results which is the output from the unittest module including stderr and stdout
python -c "a=open('%coverage_file%').read();b=a[a.index('unittest stderr and/or stdout:'):a.index('TEST COVERAGE RESULTS:')];open('unittest_results.txt','w+').write(b)"

@REM captures code coverage report which is in xml format. If there was an error running the coverage report, the error will be written to this file
python -c "a=open('%coverage_file%').read();b=a[a.index('TEST COVERAGE RESULTS:')+23:a.index('DO')];open('%coverage_file%','w+').write(b)"

docker container rm -f %container_name%