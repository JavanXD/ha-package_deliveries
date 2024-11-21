import imaplib
import email
import json
import re
from email.header import decode_header
import html
from datetime import datetime, timedelta, timezone
from zoneinfo import ZoneInfo  # Python 3.9+ provides zoneinfo for timezone handling
import argparse


# ANSI escape codes for coloring
HEADER_COLOR = '\033[95m'
OKBLUE = '\033[94m'
OKCYAN = '\033[96m'
OKGREEN = '\033[92m'
WARNING = '\033[93m'
FAIL = '\033[91m'
ENDC = '\033[0m'  # To reset color after printing

# Timezone definitions
utc = timezone.utc
cest = ZoneInfo("Europe/Berlin")  # CEST is part of Europe/Berlin

# Get today's date
today = datetime.now(cest).date()  # Using CEST time zone

deliveries = []

def convert_to_cest(email_date_str):
    """
    Converts the email date to CEST (Central European Summer Time) timezone.
    Assumes email_date is in a standard RFC2822 format, but may contain an extra (CEST).
    """
    try:
        # Remove the extra '(CEST)' from the date string, if present
        email_date_str = email_date_str.replace(' (CEST)', '')

        # Parse the email_date into a datetime object
        email_datetime = datetime.strptime(email_date_str, '%a, %d %b %Y %H:%M:%S %z')

        # Convert to CEST (Europe/Berlin timezone)
        email_datetime_cest = email_datetime.astimezone(ZoneInfo("Europe/Berlin"))

        # Return the datetime object formatted as a string
        return email_datetime_cest.strftime('%Y-%m-%d %H:%M')
    except Exception as e:
        print(f"Error converting date to CEST: {e}")
        return email_date_str  # Return original date in case of error

def decode_mime_subject(subject):
    """
    Decodes a MIME encoded subject to readable text.
    """
    decoded_subject_parts = decode_header(subject)
    decoded_subject = ''

    for part, encoding in decoded_subject_parts:
        if isinstance(part, bytes):
            # If the subject is encoded in bytes, decode it using the detected encoding
            decoded_subject += part.decode(encoding or 'utf-8')
        else:
            decoded_subject += part

    return decoded_subject


def convert_relative_date(date_str):
    weekdays = ["Montag", "Dienstag", "Mittwoch", "Donnerstag", "Freitag", "Samstag", "Sonntag"]
    months = ["Januar", "Februar", "März", "April", "Mai", "Juni", "Juli", "August", "September", "Oktober", "November", "Dezember"]

    today = datetime.now(cest).date()

    try:
        # Handle relative dates
        if "Heute" in date_str:
            date_obj = today
        elif "Morgen" in date_str:
            date_obj = today + timedelta(days=1)
        elif "Übermorgen" in date_str:
            date_obj = today + timedelta(days=2)
        else:
            # Handle date in the format like "Dienstag, 3 September"
            date_match = re.search(r'(\d{1,2})\s(\w+)', date_str)
            if date_match:
                day = int(date_match.group(1))
                month_name = date_match.group(2)
                
                # Find month number from the month name
                month = months.index(month_name) + 1
                current_year = today.year
                date_obj = datetime(current_year, month, day)
            else:
                # Handle date in the format "DD-MM" (default case)
                day, month = map(int, date_str.split('-'))
                current_year = today.year
                date_obj = datetime(current_year, month, day)

        # Format the output as "Mittwoch, 4. September"
        weekday_str = weekdays[date_obj.weekday()]
        day_str = date_obj.day
        month_str = months[date_obj.month - 1]

        return f"{weekday_str}, {day_str}. {month_str}"
    except Exception as e:
        return "Unknown"

def check_deliveries(args, mail):
    try:
        past_date = today - timedelta(days=args.last_days)
        tfmt = past_date.strftime('%d-%b-%Y')

        search_query = f'(SINCE {tfmt})'
        type, sdata = mail.search(None, search_query)
        mail_ids = sdata[0]
        id_list = mail_ids.split()

        if not id_list:
            print(f"{WARNING}No emails found matching the search criteria.{ENDC}")
            return

        # Process up to LAST_EMAILS emails
        id_list = id_list[:args.last_emails]

        print(f"{OKCYAN}Processing {len(id_list)} emails...{ENDC}")


        for i in id_list:
            typ, data = mail.fetch(i, '(RFC822)')
            for response_part in data:
                if isinstance(response_part, tuple):
                    msg = email.message_from_bytes(response_part[1])
                    
                    # Decode the subject using the helper function
                    raw_subject = msg['subject']
                    email_subject = decode_mime_subject(raw_subject)
                    
                    email_from = msg['from']
                    email_date = msg['date']
                    email_date_cest = convert_to_cest(email_date)  # Convert the date to CEST
                    email_msg = ""

                    print(f"\n{HEADER_COLOR}Email Details:{ENDC}")
                    print(f"  {OKBLUE}From:{ENDC} {email_from}")
                    print(f"  {OKGREEN}Subject:{ENDC} {email_subject}")
                    print(f"  {OKCYAN}Date:{ENDC} {email_date_cest}")

                    if msg.is_multipart():
                        email_msg = None
                        html_msg = None
                        for part in msg.walk():
                            if part.get_content_maintype() == 'multipart':
                                continue
                            if part.get_content_type() == 'text/plain':
                                email_msg = part.get_payload(decode=True).decode(part.get_content_charset() or 'utf-8', errors='replace')
                            elif part.get_content_type() == 'text/html':
                                html_msg = part.get_payload(decode=True).decode(part.get_content_charset() or 'utf-8', errors='replace')
                        if not email_msg and html_msg:
                            email_msg = html_msg
                    else:
                        email_msg = msg.get_payload(decode=True).decode(msg.get_content_charset() or 'utf-8', errors='replace')

                    # Print the email body for debugging
                    print(f"{OKCYAN}Email Body (truncated):{ENDC} {email_msg[:100]}...")

                    # Handle Amazon emails
                    if "amazon.de" in email_from.lower() and "versandt!" in email_subject:
                        print(f"{OKGREEN}Processing Amazon delivery...{ENDC}")
                        extract_amazon_delivery(email_subject, email_msg, email_date_cest)

                    # Handle DHL emails
                    elif "dhl.de" in email_from.lower() and "Sendung ist unterwegs" in email_subject:
                        print(f"{OKGREEN}Processing DHL delivery...{ENDC}")
                        extract_dhl_delivery(email_subject, email_msg, email_date_cest)

                    # Handle DPD emails
                    elif "dpd.de" in email_from.lower() and "Bald ist Ihr DPD Paket da" in email_subject:
                        print(f"{OKGREEN}Processing DPD delivery...{ENDC}")
                        extract_dpd_delivery(email_subject, email_msg, email_date_cest)

                    else:
                        print(f"{WARNING}No matching delivery service for email: {email_subject}{ENDC}")

    except Exception as e:
        print(f"{FAIL}Error checking deliveries: {e}{ENDC}")

def extract_amazon_delivery(email_subject, email_msg, email_date):
    try:
        # Extract the order number
        order_number = extract_between(email_msg, "Bestellnummer:", "\n").strip() or "Unknown"

        # Extract the tracking number and remove the trailing '.'
        tracking_number = extract_between(email_msg, "Paketverfolgungsnummern:", "\n").strip()
        tracking_number = tracking_number.rstrip('.') if tracking_number else "N/A"

        # Extract the total amount
        total_amount = extract_between(email_msg, "Gesamtbetrag der Bestellung:", "\n").strip() or "N/A"

        # Extract the delivery date
        delivery_date_match = re.search(r'Zustellung[:\s]+(?:am\s)?(\w+,\s\d+\s\w+|\d+\s\w+|\w+)', email_msg)
        if delivery_date_match:
            delivery_date = delivery_date_match.group(1).strip()
            delivery_date = convert_relative_date(delivery_date)
        else:
            delivery_date = "Unknown"

        # Extract the item list and convert to a single string, truncating each item to 45 characters
        items_section = extract_between(email_msg, "Bestellübersicht", "Verkauft von")
        max_item_length = 45

        # Process each item, and if truncated, add "..." at the end
        items_list = []
        for item in re.split(r'[\n\r]+', items_section.strip()):
            item = item.strip()
            if item:
                if len(item) > max_item_length:
                    truncated_item = item[:max_item_length - 3] + "..."  # Add "..." if item is truncated
                else:
                    truncated_item = item
                items_list.append(truncated_item)

        items = '; '.join(items_list) if items_list else "No items found"

        deliveries.append({
            "service": "Amazon",
            "order_number": order_number,
            "tracking_number": tracking_number,
            "total_amount": total_amount,
            "delivery_date": delivery_date,
            "items": items,
            "email_date": email_date
        })

        print(f"{OKGREEN}Amazon Delivery Extracted:{ENDC}")
        print(f"  {OKBLUE}Order Number:{ENDC} {order_number}")
        print(f"  {OKBLUE}Tracking Number:{ENDC} {tracking_number}")
        print(f"  {OKBLUE}Total Amount:{ENDC} {total_amount}")
        print(f"  {OKBLUE}Delivery Date:{ENDC} {delivery_date}")
        print(f"  {OKBLUE}Items:{ENDC} {items}")

    except Exception as e:
        print(f"{FAIL}Error extracting Amazon delivery: {e}{ENDC}")

def extract_dhl_delivery(email_subject, email_msg, email_date):
    try:

        # Initialize default values
        tracking_number = "Unknown"
        delivery_date = "Unknown"

        # Extract the tracking number
        tracking_number_match = re.search(r'(\d{10,})', email_msg)
        tracking_number = tracking_number_match.group(1) if tracking_number_match else "Unknown"

        # Extract the tracking number (DHL tracking numbers usually consist of 10 to 20 digits)
        tracking_number_match = re.search(r'\b\d{10,20}\b', email_msg)
        if tracking_number_match:
            tracking_number = tracking_number_match.group(0)
            
        # Extract estimated delivery date
        delivery_date_match = re.search(r'am\s\w+, den (\d{2})\.(\d{2})\.', email_msg)
        if delivery_date_match:
            day = delivery_date_match.group(1)
            month = delivery_date_match.group(2)
            # Format date to "Mittwoch, 4 September" or similar
            delivery_date = convert_relative_date(f"{day}-{month}")
        else:
            delivery_date = "Unknown"

        # Extract sender's name or details from the subject
        sender_details = extract_between(email_subject, "Ihre ", " Sendung ist unterwegs").strip() or "DHL Shipment"

        deliveries.append({
            "service": "DHL",
            "order_number": "N/A",  # DHL emails don't have order numbers
            "tracking_number": tracking_number,
            "total_amount": "N/A",  # DHL emails don't have total amounts
            "delivery_date": delivery_date,
            "items": sender_details,
            "email_date": email_date
        })

        print(f"{OKGREEN}DHL Delivery Extracted:{ENDC}")
        print(f"  {OKBLUE}Tracking Number:{ENDC} {tracking_number}")
        print(f"  {OKBLUE}Delivery Date:{ENDC} {delivery_date}")
        print(f"  {OKBLUE}Sender Details:{ENDC} {sender_details}")

    except Exception as e:
        print(f"{FAIL}Error extracting DHL delivery: {e}{ENDC}")


def extract_dpd_delivery(email_subject, email_msg, email_date):
    try:
        # Parse email_date into a datetime object using the correct format
        email_datetime = datetime.strptime(email_date, '%Y-%m-%d %H:%M')  # This matches the format of '2024-09-12 17:27:52'

        # Decode HTML entities in the email message
        decoded_email_msg = html.unescape(email_msg)

        # Extract the tracking number (both are together under "Versender & Paketnummer:")
        tracking_match = re.search(r'Versender\s&\sPaketnummer.*?>([\w\s\/\.,-]+)<.*?(\d{10,20})', decoded_email_msg)
        if tracking_match:
            sender = tracking_match.group(1).strip()
        else:
            sender = "Unknown Sender"

        # Extract the tracking number (usually consists of digits)
        tracking_number_match = re.search(r'(\d{10,20})', email_msg)
        tracking_number = tracking_number_match.group(1) if tracking_number_match else "Unknown Tracking Number"

        # Extract the delivery date (look for something like "in 1-2 Werktagen" or similar)
        delivery_window_match = re.search(r'in\s(\d+)(?:-(\d+))?\sWerktagen', email_msg)
        if delivery_window_match:
            # If there's a range, use the first number (earliest delivery day)
            delivery_days = int(delivery_window_match.group(1))  # Group 1 captures the first digit
            delivery_date = (email_datetime + timedelta(days=delivery_days)).strftime("%A, %d. %B")
        else:
            delivery_date = "Unknown"

        # Append the extracted details to the deliveries list
        deliveries.append({
            "service": "DPD",
            "order_number": "N/A",  # Not available in DPD emails
            "tracking_number": tracking_number,
            "total_amount": "N/A",  # Not available in DPD emails
            "delivery_date": delivery_date,
            "items": sender,  # Use sender as item description for DPD
            "email_date": email_date
        })

        print(f"{OKGREEN}DPD Delivery Extracted:{ENDC}")
        print(f"  {OKBLUE}Sender:{ENDC} {sender}")
        print(f"  {OKBLUE}Tracking Number:{ENDC} {tracking_number}")
        print(f"  {OKBLUE}Estimated Delivery Date:{ENDC} {delivery_date}")

    except Exception as e:
        print(f"{FAIL}Error extracting DPD delivery: {e}{ENDC}")

def extract_between(text, start, end):
    """
    Helper function to extract text between two substrings.
    """
    try:
        return text.split(start)[1].split(end)[0]
    except IndexError:
        return ""

def parse_delivery_date(delivery_date_str, email_date_str):
    """
    Parse the delivery_date if available, else use email_date.
    Ensure both are compared as `datetime.date` objects.
    """
    try:
        # Handle the 'delivery_date' format first
        if delivery_date_str and delivery_date_str != "Unknown":
            # Example: "Mittwoch, 4. September"
            date_match = re.search(r'(\d{1,2})\.\s(\w+)', delivery_date_str)
            if date_match:
                day = int(date_match.group(1))
                month_name = date_match.group(2)
                months = ["Januar", "Februar", "März", "April", "Mai", "Juni", "Juli", "August", "September", "Oktober", "November", "Dezember"]
                month = months.index(month_name) + 1
                current_year = today.year
                return datetime(current_year, month, day).date()  # Convert to datetime.date

        # If no delivery date or 'Unknown', parse email date
        email_date_obj = datetime.strptime(email_date_str, "%Y-%m-%d %H:%M")
        return email_date_obj.date()  # Ensure we return only the date part (as datetime.date)

    except Exception as e:
        return None  # Return None if date parsing fails

def merge_duplicate_deliveries(deliveries):
    """
    Merges duplicate deliveries based on tracking_number.
    Prioritizes detailed info from Amazon but keeps the latest delivery date from DHL if present.
    Extends the list of delivered items from Amazon with the same tracking number.
    Updates total_amount by concatenating prices with 'ü'.
    Separates order_number with a semicolon if there are multiple for the same tracking number.
    """
    unique_deliveries = {}
    
    for delivery in deliveries:
        tracking_number = delivery.get("tracking_number")
        
        # If the tracking number already exists, merge the details
        if tracking_number in unique_deliveries:
            existing_delivery = unique_deliveries[tracking_number]
            
            # Prefer Amazon details but update with latest DHL delivery date if newer
            if delivery["service"] == "DHL":
                # Keep the DHL delivery date if it's more recent or Amazon's is "Unknown"
                existing_delivery["delivery_date"] = delivery["delivery_date"]
            elif delivery["service"] == "Amazon":
                # Extend the items list with new items, if present
                existing_items = existing_delivery.get("items", "")
                new_items = delivery.get("items", "")
                if existing_items and new_items:
                    existing_delivery["items"] = f"{existing_items}; {new_items}"
                elif new_items:
                    existing_delivery["items"] = new_items

                # Concatenate total amounts with a "ü" in between
                existing_total_amount = existing_delivery.get("total_amount", "")
                new_total_amount = delivery.get("total_amount", "")
                if existing_total_amount and new_total_amount:
                    existing_delivery["total_amount"] = f"{existing_total_amount} + {new_total_amount}"
                elif new_total_amount:
                    existing_delivery["total_amount"] = new_total_amount

                # Concatenate order numbers with a semicolon if different
                existing_order_number = existing_delivery.get("order_number", "")
                new_order_number = delivery.get("order_number", "")
                if existing_order_number and new_order_number and existing_order_number != new_order_number:
                    existing_delivery["order_number"] = f"{existing_order_number}; {new_order_number}"
                elif new_order_number:
                    existing_delivery["order_number"] = new_order_number

        else:
            # If it's the first time seeing this tracking number, add it to unique deliveries
            unique_deliveries[tracking_number] = delivery
    
    # Convert the unique_deliveries dict back to a list
    return list(unique_deliveries.values())

def init_imap_connection(args):
    # Initialize IMAP connection
    mail = imaplib.IMAP4_SSL(args.imap_server)
    mail.login(args.email, args.password)
    mail.select(args.imap_folder)

    return mail

if __name__ == "__main__":
    """Main entry point for the script."""
    parser = argparse.ArgumentParser(description="Check package deliveries via email.")
    parser.add_argument("--email", required=True, help="Email address to log in to.")
    parser.add_argument("--password", required=True, help="Needs to be an app passwod, not your google accounts password.")
    parser.add_argument("--imap_server", default="imap.gmail.com", help="IMAP email server.")
    parser.add_argument("--last_days", type=int, default=10, help="Number of days to look back.")
    parser.add_argument("--last_emails", type=int, default=50, help="Maximum number of emails to process.")
    parser.add_argument("--imap_folder", default="INBOX", help="IMAP folder to search.")
    parser.add_argument("--output_file", default="deliveries.json", help="Path to save the deliveries JSON.")

    args = parser.parse_args()

    mail = init_imap_connection(args)

    check_deliveries(args, mail)
    
    # Remove duplicate deliveries by merging them based on tracking number
    deliveries = merge_duplicate_deliveries(deliveries)
    
    # Sort deliveries by 'delivery_date' (or 'email_date' if 'delivery_date' is not available)
    deliveries.sort(
        key=lambda x: parse_delivery_date(x['delivery_date'], x['email_date']),
        reverse=True  # Sort in descending order to have the most up-to-date or future dates on top
    )
    
    print(f"\n{HEADER_COLOR}Final Deliveries Summary (After Deduplication):{ENDC}")
    print(json.dumps(deliveries, indent=4))
    
    with open(args.output_file, 'w') as json_file:
        json.dump(deliveries, json_file)
