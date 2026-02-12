from fpdf import FPDF
from datetime import datetime

APP_NAME = "RF AI-Workshop"
CONTACT_EMAIL = "libroliclin@gmail.com"
EFFECTIVE_DATE = datetime.now().strftime("%B %d, %Y")


class PrivacyPolicyPDF(FPDF):
    def header(self):
        self.set_font("Helvetica", "B", 12)
        self.cell(0, 10, f"Privacy Policy - {APP_NAME}", align="C", new_x="LMARGIN", new_y="NEXT")
        self.ln(2)

    def footer(self):
        self.set_y(-15)
        self.set_font("Helvetica", "I", 8)
        self.cell(0, 10, f"Page {self.page_no()}/{{nb}}", align="C")

    def section_title(self, title):
        self.set_font("Helvetica", "B", 12)
        self.cell(0, 10, title, new_x="LMARGIN", new_y="NEXT")
        self.ln(1)

    def section_body(self, text):
        self.set_font("Helvetica", "", 10)
        self.multi_cell(0, 6, text)
        self.ln(4)


pdf = PrivacyPolicyPDF()
pdf.alias_nb_pages()
pdf.set_auto_page_break(auto=True, margin=15)
pdf.add_page()

# Title
pdf.set_font("Helvetica", "B", 18)
pdf.cell(0, 15, "Privacy Policy", align="C", new_x="LMARGIN", new_y="NEXT")
pdf.set_font("Helvetica", "", 11)
pdf.cell(0, 8, f"for {APP_NAME}", align="C", new_x="LMARGIN", new_y="NEXT")
pdf.cell(0, 8, f"Effective Date: {EFFECTIVE_DATE}", align="C", new_x="LMARGIN", new_y="NEXT")
pdf.ln(10)

# 1. Introduction
pdf.section_title("1. Introduction")
pdf.section_body(
    f'Welcome to {APP_NAME}. This Privacy Policy explains how we collect, use, disclose, '
    f'and safeguard your information when you use our application integrated with Meta (Facebook) '
    f'platform services. Please read this privacy policy carefully. By using {APP_NAME}, you '
    f'agree to the collection and use of information in accordance with this policy.'
)

# 2. Information We Collect
pdf.section_title("2. Information We Collect")
pdf.section_body(
    "We may collect the following types of information:\n\n"
    "a) Information from Meta Platform:\n"
    "   - Your public profile information (name, profile picture)\n"
    "   - Email address associated with your Meta account\n"
    "   - Page and account information you grant access to\n\n"
    "b) Usage Data:\n"
    "   - Log data such as access times and pages viewed\n"
    "   - Device information (device type, operating system)\n"
    "   - IP address and browser type\n\n"
    "c) User-Provided Data:\n"
    "   - Any content or data you voluntarily provide through the app"
)

# 3. How We Use Your Information
pdf.section_title("3. How We Use Your Information")
pdf.section_body(
    "We use the collected information for the following purposes:\n\n"
    "- To provide, operate, and maintain our application\n"
    "- To improve, personalize, and expand our application\n"
    "- To understand and analyze how you use our application\n"
    "- To communicate with you for customer service and support\n"
    "- To process your transactions and requests\n"
    "- To comply with legal obligations"
)

# 4. Data Sharing and Disclosure
pdf.section_title("4. Data Sharing and Disclosure")
pdf.section_body(
    "We do not sell, trade, or rent your personal information to third parties. "
    "We may share your information only in the following circumstances:\n\n"
    "- With your explicit consent\n"
    "- To comply with legal obligations or respond to lawful requests\n"
    "- To protect and defend our rights or property\n"
    "- To prevent fraud or address security issues\n"
    "- With service providers who assist in operating our application, "
    "subject to confidentiality agreements"
)

# 5. Data Retention
pdf.section_title("5. Data Retention")
pdf.section_body(
    "We retain your personal information only for as long as necessary to fulfill the "
    "purposes outlined in this Privacy Policy, unless a longer retention period is required "
    "or permitted by law. When your data is no longer needed, we will securely delete or "
    "anonymize it."
)

# 6. Data Security
pdf.section_title("6. Data Security")
pdf.section_body(
    "We implement appropriate technical and organizational security measures to protect "
    "your personal information against unauthorized access, alteration, disclosure, or "
    "destruction. However, no method of transmission over the Internet or electronic "
    "storage is 100% secure, and we cannot guarantee absolute security."
)

# 7. Your Rights
pdf.section_title("7. Your Rights")
pdf.section_body(
    "You have the following rights regarding your personal data:\n\n"
    "- Access: You can request a copy of your personal data we hold\n"
    "- Correction: You can request correction of inaccurate data\n"
    "- Deletion: You can request deletion of your personal data\n"
    "- Data Portability: You can request a portable copy of your data\n"
    "- Withdraw Consent: You can withdraw your consent at any time\n\n"
    f"To exercise any of these rights, please contact us at {CONTACT_EMAIL}."
)

# 8. Data Deletion
pdf.section_title("8. Data Deletion")
pdf.section_body(
    f"You may request deletion of your data at any time by contacting us at "
    f"{CONTACT_EMAIL}. Upon receiving your request, we will delete your personal "
    f"data within 30 days, unless we are required by law to retain certain information. "
    f"You can also remove our app's access to your Meta account through your Facebook "
    f"Settings > Apps and Websites."
)

# 9. Third-Party Services
pdf.section_title("9. Third-Party Services")
pdf.section_body(
    "Our application may integrate with third-party services, including Meta Platform "
    "services. These third-party services have their own privacy policies, and we "
    "encourage you to review them. We are not responsible for the privacy practices "
    "of third-party services."
)

# 10. Children's Privacy
pdf.section_title("10. Children's Privacy")
pdf.section_body(
    "Our application is not intended for children under the age of 13. We do not "
    "knowingly collect personal information from children under 13. If we discover "
    "that a child under 13 has provided us with personal information, we will "
    "promptly delete it."
)

# 11. Changes to This Policy
pdf.section_title("11. Changes to This Privacy Policy")
pdf.section_body(
    "We may update this Privacy Policy from time to time. We will notify you of any "
    "changes by posting the new Privacy Policy within the application and updating the "
    "\"Effective Date\" at the top. You are advised to review this Privacy Policy "
    "periodically for any changes."
)

# 12. Contact Us
pdf.section_title("12. Contact Us")
pdf.section_body(
    f"If you have any questions or concerns about this Privacy Policy or our data "
    f"practices, please contact us at:\n\n"
    f"Application: {APP_NAME}\n"
    f"Email: {CONTACT_EMAIL}"
)

output_path = "privacy_policy_rf_ai_workshop.pdf"
pdf.output(output_path)
print(f"Privacy Policy PDF generated: {output_path}")
