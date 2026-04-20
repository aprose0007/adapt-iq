# Use the official Python 3.10 image
FROM python:3.10-slim

# Set working directory
WORKDIR /app

# Expose the port Hugging Face Spaces expects
EXPOSE 7860

# Install dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Create a non-root user that Hugging Face Spaces requires
RUN useradd -m -u 1000 user
USER user
ENV PATH="/home/user/.local/bin:$PATH"

# Copy the rest of the application code
COPY --chown=user . .

# Run the application with Gunicorn
CMD ["gunicorn", "-b", "0.0.0.0:7860", "app:app", "--timeout", "120"]
