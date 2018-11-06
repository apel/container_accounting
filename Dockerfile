FROM centos:7
MAINTAINER APEL Administrators <apel-admins@stfc.ac.uk>

# Copy the container_accounting Git repository to /usr/share/container_accounting
COPY . /usr/share/container_accounting
# Then set /usr/share/container_accounting as the working directory
WORKDIR /usr/share/container_accounting

# Add the EPEL repo so we can get pip
RUN yum -y install epel-release
# Then get pip
RUN yum -y install python-pip

# Install the python requirements of container_accounting
RUN pip install -r requirements.txt

# Set PYTHONPATH so Python can import the necessary files at run time. 
ENV PYTHONPATH=/usr/share/container_accounting

# To avoid running the container as root, create an apel user.
RUN useradd -s /bin/bash apel
# Allow the apel user to run the container accounting software.
RUN chown -R apel:apel /usr/share/container_accounting
# Set the default user of the container to apel.
USER apel:apel

ENTRYPOINT ./entrypoint.sh 
