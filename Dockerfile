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
