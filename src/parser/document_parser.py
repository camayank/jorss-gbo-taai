"""
Document parser for tax forms (W-2, 1099, etc.)
Supports PDF and image files with OCR capability
"""
import re
from typing import Optional, Dict, List
from pathlib import Path
import pdfplumber
from PIL import Image
import pytesseract

from ..models.income import W2Info, Form1099Info


class DocumentParser:
    """Parse tax documents to extract structured information"""
    
    def __init__(self):
        self.ocr_enabled = True
    
    def parse_w2(self, file_path: str) -> Optional[W2Info]:
        """
        Parse a W-2 form from PDF or image
        Returns W2Info object with extracted data
        """
        text = self._extract_text(file_path)
        if not text:
            return None
        
        # Extract W-2 information using regex patterns
        w2_data = {}
        
        # Employer name (usually at top)
        employer_match = re.search(r'Employer\'?s name[:\s]+([A-Za-z0-9\s&,\.\-]+)', text, re.IGNORECASE)
        if employer_match:
            w2_data['employer_name'] = employer_match.group(1).strip()
        
        # EIN
        ein_match = re.search(r'EIN[:\s]+([0-9\-]+)', text, re.IGNORECASE)
        if ein_match:
            w2_data['employer_ein'] = ein_match.group(1).strip()
        
        # Box 1: Wages
        wages_match = re.search(r'Box\s*1[:\s]+([0-9,]+\.?[0-9]*)', text, re.IGNORECASE)
        if wages_match:
            w2_data['wages'] = float(wages_match.group(1).replace(',', ''))
        
        # Box 2: Federal tax withheld
        fed_tax_match = re.search(r'Box\s*2[:\s]+([0-9,]+\.?[0-9]*)', text, re.IGNORECASE)
        if fed_tax_match:
            w2_data['federal_tax_withheld'] = float(fed_tax_match.group(1).replace(',', ''))
        
        # Box 3: Social Security wages
        ss_wages_match = re.search(r'Box\s*3[:\s]+([0-9,]+\.?[0-9]*)', text, re.IGNORECASE)
        if ss_wages_match:
            w2_data['social_security_wages'] = float(ss_wages_match.group(1).replace(',', ''))
        
        # Box 4: Social Security tax withheld
        ss_tax_match = re.search(r'Box\s*4[:\s]+([0-9,]+\.?[0-9]*)', text, re.IGNORECASE)
        if ss_tax_match:
            w2_data['social_security_tax_withheld'] = float(ss_tax_match.group(1).replace(',', ''))
        
        # Box 5: Medicare wages
        medicare_wages_match = re.search(r'Box\s*5[:\s]+([0-9,]+\.?[0-9]*)', text, re.IGNORECASE)
        if medicare_wages_match:
            w2_data['medicare_wages'] = float(medicare_wages_match.group(1).replace(',', ''))
        
        # Box 6: Medicare tax withheld
        medicare_tax_match = re.search(r'Box\s*6[:\s]+([0-9,]+\.?[0-9]*)', text, re.IGNORECASE)
        if medicare_tax_match:
            w2_data['medicare_tax_withheld'] = float(medicare_tax_match.group(1).replace(',', ''))
        
        # State information (varies by state)
        state_wages_match = re.search(r'State\s+wages[:\s]+([0-9,]+\.?[0-9]*)', text, re.IGNORECASE)
        if state_wages_match:
            w2_data['state_wages'] = float(state_wages_match.group(1).replace(',', ''))
        
        state_tax_match = re.search(r'State\s+tax[:\s]+([0-9,]+\.?[0-9]*)', text, re.IGNORECASE)
        if state_tax_match:
            w2_data['state_tax_withheld'] = float(state_tax_match.group(1).replace(',', ''))
        
        # Create W2Info object
        try:
            return W2Info(
                employer_name=w2_data.get('employer_name', 'Unknown Employer'),
                employer_ein=w2_data.get('employer_ein'),
                wages=w2_data.get('wages', 0.0),
                federal_tax_withheld=w2_data.get('federal_tax_withheld', 0.0),
                social_security_wages=w2_data.get('social_security_wages'),
                social_security_tax_withheld=w2_data.get('social_security_tax_withheld'),
                medicare_wages=w2_data.get('medicare_wages'),
                medicare_tax_withheld=w2_data.get('medicare_tax_withheld'),
                state_wages=w2_data.get('state_wages'),
                state_tax_withheld=w2_data.get('state_tax_withheld'),
            )
        except Exception as e:
            print(f"Error creating W2Info: {e}")
            return None
    
    def parse_1099(self, file_path: str, form_type: str = "1099-MISC") -> Optional[Form1099Info]:
        """
        Parse a 1099 form from PDF or image
        """
        text = self._extract_text(file_path)
        if not text:
            return None
        
        # Extract 1099 information
        data = {}
        
        # Payer name
        payer_match = re.search(r'Payer\'?s name[:\s]+([A-Za-z0-9\s&,\.\-]+)', text, re.IGNORECASE)
        if payer_match:
            data['payer_name'] = payer_match.group(1).strip()
        
        # TIN
        tin_match = re.search(r'TIN[:\s]+([0-9\-]+)', text, re.IGNORECASE)
        if tin_match:
            data['payer_tin'] = tin_match.group(1).strip()
        
        # Amount (varies by 1099 type)
        amount_match = re.search(r'Amount[:\s]+([0-9,]+\.?[0-9]*)', text, re.IGNORECASE)
        if amount_match:
            data['amount'] = float(amount_match.group(1).replace(',', ''))
        
        try:
            return Form1099Info(
                payer_name=data.get('payer_name', 'Unknown Payer'),
                payer_tin=data.get('payer_tin'),
                form_type=form_type,
                amount=data.get('amount', 0.0),
            )
        except Exception as e:
            print(f"Error creating Form1099Info: {e}")
            return None
    
    def _extract_text(self, file_path: str) -> str:
        """Extract text from PDF or image file"""
        path = Path(file_path)
        
        if not path.exists():
            return ""
        
        text = ""
        
        # Try PDF first
        if path.suffix.lower() == '.pdf':
            try:
                with pdfplumber.open(file_path) as pdf:
                    for page in pdf.pages:
                        text += page.extract_text() or ""
            except Exception as e:
                print(f"Error reading PDF: {e}")
        
        # Try image with OCR
        elif path.suffix.lower() in ['.jpg', '.jpeg', '.png', '.tiff', '.bmp']:
            try:
                image = Image.open(file_path)
                if self.ocr_enabled:
                    text = pytesseract.image_to_string(image)
                else:
                    return ""
            except Exception as e:
                print(f"Error reading image: {e}")
        
        return text
