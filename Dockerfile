# Use the official Python image from the Docker Hub
FROM python:3.12


RUN set -ex; \
    apt-get -y update; \
    apt-get -y install imagemagick ffmpeg fonts-liberation; \
    # Allow read/write access to /tmp directory
    echo "<policy domain=\"path\" rights=\"read|write\" pattern=\"@/tmp/*\" />" >> /etc/ImageMagick-6/policy.xml; \
    echo "<policy domain=\"path\" rights=\"read|write\" pattern=\"/tmp/*\" />" >> /etc/ImageMagick-6/policy.xml; \
    # Allow some image formats and operations
    echo "<policy domain=\"coder\" rights=\"read|write\" pattern=\"*\" />" >> /etc/ImageMagick-6/policy.xml; \
    echo "<policy domain=\"system\" rights=\"read|write\" pattern=\"*\" />" >> /etc/ImageMagick-6/policy.xml; \
    # Remove restrictions on using temporary files
    echo "<policy domain=\"resource\" name=\"temporary-path\" value=\"/tmp\" />" >> /etc/ImageMagick-6/policy.xml; \
    rm -rf /var/lib/apt/lists/*

# Set the working directory in the container
WORKDIR /app

# Copy the requirements file into the container
COPY requirements.txt .

# Install the dependencies
RUN pip install --no-cache-dir -r requirements.txt


# Copy the rest of the application code into the container
COPY . .

# Set environment variables
ENV PORT 8080

# Expose the port the app runs on
EXPOSE 8080

# Define the command to run the application
CMD ["gunicorn", "-w", "4", "-b", "0.0.0.0:8080", "--timeout", "600", "app:create_app()"]
