#!/bin/bash

# Colorful Output
GREEN='\033[0;32m'
CYAN='\033[0;36m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m' # No Color

echo -e "${CYAN}==========================================${NC}"
echo -e "${CYAN}   Molty Royale AI Agent Installer        ${NC}"
echo -e "${CYAN}==========================================${NC}"

# 1. System Check & Dependencies
echo -e "${YELLOW}[1/4] Checking Python 3 and Pip...${NC}"

if ! command -v python3 &> /dev/null
then
    echo -e "${RED}Python3 could not be found. Installing...${NC}"
    sudo apt update
    sudo apt install -y python3 python3-pip python3-venv
else
    echo -e "${GREEN}Python3 is installed.${NC}"
fi

# 2. Virtual Environment Setup
echo -e "${YELLOW}[2/4] Setting up Python Virtual Environment...${NC}"
if [ ! -d "venv" ]; then
    python3 -m venv venv
    echo -e "${GREEN}Created virtual environment 'venv'.${NC}"
fi

echo "Activating virtual environment..."
source venv/bin/activate

# 3. Install Requirements
echo -e "${YELLOW}[3/4] Installing dependencies...${NC}"
if [ -f "requirements.txt" ]; then
    pip3 install -r requirements.txt
    echo -e "${GREEN}Dependencies installed successfully!${NC}"
else
    echo -e "${RED}Error: requirements.txt not found!${NC}"
    exit 1
fi

# 4. Interactive Configuration
echo -e "${YELLOW}[4/4] Configuration Setup${NC}"

read -p "Enter your mr_live_ API Key: " API_KEY

if [[ ! $API_KEY == mr_live_* ]]; then
    echo -e "${RED}Invalid API Key format! Must start with mr_live_${NC}"
    exit 1
fi

echo -e "${CYAN}Select the type of room you wish to join:${NC}"
echo "1) Free Room"
echo "2) Paid Room (Requires On-Chain Tx manually after signature)"
read -p "Enter choice (1 or 2): " ROOM_CHOICE

if [ "$ROOM_CHOICE" == "2" ]; then
    ROOM_TYPE="paid"
else
    ROOM_TYPE="free"
fi

echo -e "${GREEN}Awesome! Initializing the AI Bot in ${ROOM_TYPE} mode...${NC}"
echo -e "${CYAN}==========================================${NC}"

# Execute Bot
python3 main.py --api-key "$API_KEY" --room-type "$ROOM_TYPE"
