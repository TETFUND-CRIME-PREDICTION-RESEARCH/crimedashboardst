#!/bin/sh

# Load environment variables from .env file
if [ -f .env ]; then
  export $(cat .env | xargs)
fi

# Run the Streamlit app
exec streamlit run main.py 
