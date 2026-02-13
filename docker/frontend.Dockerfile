FROM node:20-alpine

# Set work directory
WORKDIR /app

# Copy package files
COPY frontend/package*.json ./

# Install dependencies
RUN npm ci

# Copy project files
COPY frontend/ .

# Build app
RUN npm run build

# Start app
CMD ["npm", "start"]