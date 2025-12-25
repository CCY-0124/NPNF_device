#!/usr/bin/env python3

import requests
import os
import json
from datetime import datetime, timedelta
from pathlib import Path

# Load configuration from file if available
CONFIG_FILE = Path(__file__).parent / 'device_config.json'
API_BASE = "http://localhost:3001/api"  # Default, can be overridden by config

# Try to load API URL from config file
if CONFIG_FILE.exists():
    try:
        with open(CONFIG_FILE, 'r') as f:
            config = json.load(f)
            api_url = config.get('api_url', '').rstrip('/')
            if api_url:
                API_BASE = f"{api_url}/api"
    except PermissionError:
        # Permission denied - file might be owned by different user
        # Try to fix permissions or use default
        import os
        try:
            # Try to make file readable
            os.chmod(CONFIG_FILE, 0o644)
            with open(CONFIG_FILE, 'r') as f:
                config = json.load(f)
                api_url = config.get('api_url', '').rstrip('/')
                if api_url:
                    API_BASE = f"{api_url}/api"
        except:
            # If still can't read, use default API_BASE
            pass
    except (json.JSONDecodeError, KeyError):
        pass  # Use default if config file is invalid

def fetch_device_data(device_token, start_date, end_date):
    """
    Fetch device config and todos from API.
    
    Args:
        device_token: The device token from e-ink device configuration
        start_date: Start date in 'YYYY-MM-DD' format
        end_date: End date in 'YYYY-MM-DD' format
    
    Returns:
        dict with 'config' and 'todos' keys, or None on error
    """
    url = f"{API_BASE}/calendar-shares/devices/view/{device_token}"
    params = {
        'startDate': start_date,
        'endDate': end_date
    }
    
    try:
        response = requests.get(url, params=params, timeout=10)
        response.raise_for_status()
        return response.json()
    except requests.RequestException as e:
        print(f"Error fetching data: {e}")
        if hasattr(e, 'response') and e.response is not None:
            try:
                error_data = e.response.json()
                print(f"Error details: {error_data}")
            except:
                print(f"Response status: {e.response.status_code}")
        return None

def get_weekly_data(device_token, week_start_date=None):
    """
    Get weekly data for a specific week.
    
    Args:
        device_token: The device token
        week_start_date: Monday date (datetime object). If None, uses current week's Monday.
    
    Returns:
        dict with config and todos, or None on error
    """
    if week_start_date is None:
        today = datetime.now()
        days_since_monday = today.weekday()
        week_start_date = today - timedelta(days=days_since_monday)
    
    start_date = week_start_date.strftime('%Y-%m-%d')
    end_date = (week_start_date + timedelta(days=6)).strftime('%Y-%m-%d')
    
    return fetch_device_data(device_token, start_date, end_date)

def get_monthly_data(device_token, month_date=None):
    """
    Get monthly data for a specific month.
    
    Args:
        device_token: The device token
        month_date: Date in the month (datetime object). If None, uses current month.
    
    Returns:
        dict with config and todos, or None on error
    """
    if month_date is None:
        today = datetime.now()
        month_date = today.replace(day=1)
    
    first_day = month_date.replace(day=1)
    last_day = (first_day.replace(day=28) + timedelta(days=4)).replace(day=1) - timedelta(days=1)
    
    start_date = first_day.strftime('%Y-%m-%d')
    end_date = last_day.strftime('%Y-%m-%d')
    
    return fetch_device_data(device_token, start_date, end_date)

def get_yearly_data(device_token, year=None):
    """
    Get yearly data for a specific year.
    
    Args:
        device_token: The device token
        year: Year (int). If None, uses current year.
    
    Returns:
        dict with config and todos, or None on error
    """
    if year is None:
        year = datetime.now().year
    
    start_date = f"{year}-01-01"
    end_date = f"{year}-12-31"
    
    return fetch_device_data(device_token, start_date, end_date)

