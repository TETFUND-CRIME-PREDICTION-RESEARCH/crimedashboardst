# Use the official Python image from the Docker Hub
FROM python:3.9-slim

# Set the working directory
WORKDIR /app

# Copy the requirements file
COPY requirements.txt requirements.txt

# Install dependencies
RUN pip install -r requirements.txt

# Copy the application files
COPY . .

# Make entrypoint.sh executable
RUN chmod +x entrypoint.sh

# Expose the port the app runs on
EXPOSE 8501

# Run the entrypoint script
ENTRYPOINT ["./entrypoint.sh"]
