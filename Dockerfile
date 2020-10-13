FROM centos:7
MAINTAINER APEL Administrators <apel-admins@stfc.ac.uk>

# Copy the container_accounting Git repository to /usr/share/container_accounting
COPY . /usr/share/container_accounting
# Then set /usr/share/container_accounting as the working directory
WORKDIR /usr/share/container_accounting

# Get python3
RUN yum -y install python3

# Install the python requirements of container accounting
RUN pip3 install -r ./requirements.txt

# Set PYTHONPATH so Python can import the necessary files at run time.
ENV PYTHONPATH=/usr/share/container_accounting

# To avoid running the container as root, create an apel user.
RUN useradd -s /bin/bash apel
# Allow the apel user to run the container accounting software.
RUN chown -R apel:apel /usr/share/container_accounting
# Set the default user of the container to apel.
USER apel:apel

# Set a healthcheck for this container, and give the container 30 seconds
# after start up where the health of the container will not be checked.
# This makes it likely the underlying python call will have returned at least
# once before the health check is called.
HEALTHCHECK --start-period=30s CMD ./healthcheck.sh

ENTRYPOINT ./entrypoint.sh
