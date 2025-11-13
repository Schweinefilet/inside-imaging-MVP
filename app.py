# app.py
import os
import io
import re
import json
import logging
import boto3
from botocore.config import Config

# load .env early
from dotenv import load_dotenv
load_dotenv(dotenv_path=".env", override=True)

from flask import (
    Flask,
    render_template,
    request,
    redirect,
    url_for,
    flash,
    session,
    make_response,
    jsonify,
    abort,
)
from werkzeug.utils import secure_filename
from werkzeug.security import generate_password_hash, check_password_hash
from flask_cors import CORS

# local db
from src import db

_AWS_REGION = os.getenv("AWS_REGION") or os.getenv("AWS_DEFAULT_REGION") or "us-east-1"

_textract_client = None
def _textract():
    global _textract_client
    if _textract_client is None:
        _textract_client = None
        def _textract():
            global _textract_client
            if _textract_client is None:
                _textract_client = boto3.client(
                    "textract",
                    region_name=_AWS_REGION,
                    config=Config(retries={"max_attempts": 3, "mode": "standard"})
                )
            return _textract_client
logging.info("INSIDEIMAGING_ALLOW_LLM=%r", os.getenv("INSIDEIMAGING_ALLOW_LLM"))
logging.info("OPENAI_MODEL=%r", os.getenv("OPENAI_MODEL"))

# Set default model to gpt-5 if not specified
if not os.getenv("OPENAI_MODEL"):
    os.environ["OPENAI_MODEL"] = "gpt-5"
    logging.info("Defaulting OPENAI_MODEL to gpt-5")

# --- app ---
app = Flask(__name__)
app.secret_key = os.environ.get("SECRET_KEY", "supersecretkey")

# CORS
CORS(app, resources={r"/*": {"origins": os.getenv("CORS_ORIGINS", "https://schweinefilet.github.io")}})

# available languages
LANGUAGES = ["English", "Kiswahili"]

# pricing + tokens
USD_PER_REPORT = 1.00
KES_PER_USD = 129
TOKENS_PER_REPORT = 1

# curated content for magazine + blog pages
MAGAZINE_ISSUES = [
    {
        "title": "July 2025 · THE FUTURE OF AI IN IMAGING",
        "url": "magazine/July-2025.pdf",
        "note": "Upload static/magazine/July-2025.pdf",
    },
]

BLOG_POSTS = [
    {
        "title": "Excellence in Radiography: My Journey as a Valedictorian and Beyond",
        "summary": "A personal reflection on the path to excellence in radiography, exploring the dedication, challenges, and triumphs that shaped a distinguished career in medical imaging.",
        "author": "Mbuya Benjamin",
        "author_bio": "Valedictorian and accomplished radiographer sharing insights on professional growth and excellence in medical imaging.",
        "author_image": None,
        "author_linkedin": None,
        "author_twitter": None,
        "author_facebook": None,
        "author_whatsapp": None,
        "author_email": "editor@insideimaging.example",
        "author_website": None,
        "date": "July 2025",
        "read_time": "7 min read",
        "url": "/magazine#page=9",
        "author_qualifications": "BSc Radiography (Radiotherapy), Valedictorian (JKUAT)",
        "content": """
<h3>Introduction</h3>
<p>
  My name is Mbuya Benjamin; I had the honor to be named the valedictorian of the
  JKUAT 41st Graduation Ceremony held in December 2023. I hold a Bachelors of
  Radiography (Radiotherapy option). I am deeply fascinated with healthcare and
  technology; that motivated me to pursue Radiography. As I grew up, I looked up to
  how vital radiologists and radiographers were in diagnosing and saving lives
  through their expertise in imaging; that was the path I wanted to follow. At JKUAT,
  though challenging to navigate, I met many obstacles and opportunities that
  spearheaded my growth. Being the valedictorian is not only a personal success
  but also a bigger testament to the never-ending encouragement from my family,
  peers and mentors.
</p>

<h3>Academic Journey and Key Milestones</h3>
<p>
  Being a Radiography student at JKUAT was intellectually stimulating and emotionally
  demanding at the same time. As medical technologies became more complex, mastering
  the coursework was quickly overshadowed by the requisite of learning how to use
  these complex, life-saving technologies. An early hurdle I hit was to have to make
  up the difference between academic work and acquiring hands-on experience through
  clinical placements and internships. However, these real-world experiences are some
  of the most rewarding experiences I have had where I could use theoretical knowledge
  in the clinical setting.
</p>
<p>
  Besides this, I had the opportunity to embark on cutting-edge research to evaluate
  the implications of radiotherapy treatment for patients with head and neck tumors.
  This project was tremendously gratifying for the achievement and my love for
  innovativeness in healthcare.
</p>
<p>
  My clinical placements were attended at KNH, and my internship was at Nakuru
  Regional Cancer Centre. This gave me invaluably diverse exposure to how radiotherapy
  was practiced worldwide, and the firsthand experience was exactly how things like
  technology make for a more accurate diagnosis and better therapy. My involvement in
  community outreach programmes also gave me an understanding of how radiography and
  healthcare services affect the community.
</p>

<h3>Advice to Aspiring Radiographers</h3>
<p>
  I have adapted to sudden change by learning to make the most of the time and
  persevere. The more challenges and each obstacle faced helped shape the person I
  am today, and I discovered and appreciated what it meant to excel in practice and
  theory. At JKUAT I developed leadership skills through serving in various leadership
  capacities such as; College Representative for the Coll ege of Health Sciences,
  School Student Representative for the School of Biomedical Sciences and also the
  Chairperson for the KYGN JKUAT Chapter.
</p>
<p>
  am excited to enter the profession at such a time of technology-altering healthcare.
  I am also happy to join a dynamic and changing field for the better. The opening
  of new frontiers for more accurate and efficient diagnoses, such as artificial
  intelligence (AI), 3D imaging, digital radiography and Advanced Radiotherapy
  Techniques comes through such advances. Seeing these works being adopted in major
  medical centres in Kenya allows us to take a step in the right direction and
  continue providing good quality patient care.
</p>
<p>
  From what I see, the profession still needs constant reinforcement of the continuing
  education and professional development. Thus, healthcare technology will develop,
  and radiographers will need to keep up to date and ahead of the new rates of
  technology to be able to use these new methods correctly. Moreover, more specific
  radiography fields, for example, Forensic, Industrial or Veterinary Radiography
  still require further expertise. However, emphasis should be placed on integrating
  radiography education with primordial experience. Partnerships with hospitals,
  research institutions, and technology providers will be needed to ensure students
  are prepared for the rapidly changing healthcare environment. A bridge between the
  needs of patients and healthcare providers and the learning of future radiographers
  will assist in bridging the gap between academia and industry.
</p>
<p>
  Stay curious and learn for those who hope to become radiographers. It can be a
  demanding field, but offering equally rewarding prospects. Radiographers are
  essential to patient care, and success in this profession depends on mastering both
  the technical and interpersonal sides of the profession.
</p>
<p>
  Networking is another critical factor. Form relationships with your lecturers,
  mentors and fellow students; your peers today could be your colleagues and
  collaborators tomorrow. You will get new inspirations by participating in
  conferences, workshops, and online forums with professionals who are familiar
  with radiography.
</p>

<h3>Conclusion</h3>
<p>
  Finally, the journey to excellence in radiography is individualized. This is about
  committing to becoming a master of technical skills, continuing to learn for a
  lifetime, and being passionate about improving the outcomes of the patients. In our
  role as young professionals, we have a responsibility to continue upholding the high
  standards of profession not only in our education but by contributing to furthering
  healthcare in the country and improving upon it wherever possible. I urge all those
  who wish to become radiographers to keep pushing for excellence, embrace new
  challenges, and feel a sense of pride at the profound impact we can have on the
  health and well-being of others.
</p>

    """,
    },
    {
        "title": "AI in Medical Radiography, Imaging and Radiotherapy: Innovations and Ethical Considerations",
        "summary": "Exploring the transformative impact of artificial intelligence in medical imaging and radiotherapy, while addressing the critical ethical considerations that must guide its implementation.",
        "author": "Jevas Kenyanya",
        "author_bio": "Medical imaging specialist focused on AI integration and ethical frameworks in healthcare technology.",
        "author_image": None,
        "author_linkedin": None,
        "author_twitter": None,
        "author_facebook": None,
        "author_whatsapp": None,
        "author_email": "editor@insideimaging.example",
        "author_website": None,
        "date": "July 2025",
        "read_time": "10 min read",
        "url": "/magazine#page=18",
        "author_qualifications": "President Society of Radiography in Kenya (SORK)",
        "content": """
<h3>Introduction</h3>
<p>
  Artificial Intelligence (AI) uses computers to model intelligent behaviors with minimal human
  intervention, enabling tasks such as decision-making and prediction (Ayorinde et al., 2024).
  As a data-driven paradigm, AI aligns seamlessly with technology-driven fields like
  radiography (Hardy & Harvey, 2020). Radiographers are members of the multidisciplinary
  healthcare team, educated, clinically competent, and legally authorized to perform
  radiography, medical imaging, and radiotherapy procedures for diagnostic, therapeutic, and
  research purposes using ionizing radiation, sound waves, magnetically induced signals, or
  radioactive materials (International Society of Radiographers and Radiological
  Technologists, 2021).
</p>
<p>
  Radiographers bridge technology and patient care by operating advanced imaging and
  radiotherapy equipment while ensuring patient safety, positioning them as key agents in AI
  integration (Akudjedu et al., 2023; Stogiannos et al., 2025). The vast patient data generated
  in radiography practices supports big data analytics and machine learning, driving the
  development of AI-driven diagnostic tools. This expertise makes radiographers essential in
  implementing AI to enhance diagnostic accuracy, efficiency, and overall healthcare delivery
  (Hardy & Harvey, 2020).
</p>

<h3>The Future of AI in Medical Radiography, Imaging, and Radiotherapy</h3>
<p>
  The increase in the burden of lifestyle diseases, rising healthcare costs, and challenges such
  as pandemics, conflicts, and workforce shortages globally is driving the need for AI-driven
  interventions (ShiftMed Team, 2024). Therefore, the application of AI in medicine has come
  to revolutionize and fast-track the achievement of the quadruple aims of healthcare: to
  improve population health, enhance patient care, support providers, and reduce healthcare
  costs (Colvin, 2020). For example, AI is transforming medical imaging and radiotherapy by
  enhancing diagnostics, optimizing workflows, reducing errors, and improving efficiency
  (Bajwa, 2021).
</p>
<p>
  AI tools can analyze large datasets generated in clinical areas, predict outcomes, and
  recommend treatments with greater accuracy (Colvin, 2020). The incorporation of AI insights
  in medical imaging and radiotherapy has supported better diagnosis, treatment protocols,
  workflow efficiency, and referral systems (Bajwa, 2021). From a radiographer’s perspective,
  AI applications span the entire imaging workflow, from pre-examination planning to image
  acquisition and post-processing and beyond (Akudjedu et al., 2023). This underscores the
  surge of AI applications into the radiographers’ clinical practice.
</p>
 

<h3>Pre-examination assessment</h3>
<p>
  Radiographers play an essential role in patient care before, during, and after imaging or
  radiotherapy procedures. While AI cannot replace these responsibilities, it enhances
  efficiency by automating patient queue management, vetting referrals, and validating
  clinical indications against appropriate imaging modalities and techniques. Additionally, AI
  interacts with electronic health records to verify patient identification, streamlining
  workflows and improving overall radiographer efficiency.
</p>

<h3>Examination planning</h3>
<p>
  AI optimizes patient parameters through intelligent systems, supporting personalized
  healthcare during imaging planning. AI aids radiographers in carrying out their roles, like
  patient positioning, contrast administration, and protocol selection, subsequently enhancing
  precision and efficiency in imaging procedures.
</p>

<h3>Image acquisition</h3>
<p>
  Selecting the appropriate imaging protocol based on patient presentation, clinical
  questions, and the region of interest is a key responsibility of radiographers. However,
  protocols vary across hospitals, imaging modalities, and individual radiographers.
  Automating imaging protocols and dose optimization through AI software will help
  standardize the practices, reduce turnaround times, and enhance patient safety.
</p>

<h3>Image processing</h3>
<p>
  AI enhances medical imaging by automating post-processing, improving image quality,
  segmenting anatomical structures, and detecting abnormalities, reducing radiographers'
  workload. It aids in triaging by flagging critical cases for faster review, improving workflow
  efficiency. Machine learning models identify disease patterns, supporting early detection
  and decision-making. AI-driven synthetic modality transfer enables the conversion of images
  between modalities (e.g., CT to MRI), thereby minimizing radiation exposure and reducing
  the need for repeat scans. Additionally, AI ensures consistency in image interpretation,
  standardizes quality control, and eliminates interpersonal variability across healthcare
  facilities (Mohammad et al., 2024; Colvin, 2020).
</p>

<h3>The Paradigm to Radiographers’ Perceptions of AI</h3>
<p>
  Several studies have been conducted globally to explore radiographers' levels of knowledge,
  perspectives, and expectations regarding AI applications in radiography, imaging, and
  radiotherapy. According to Akudjedu et al. (2023), a lack of AI applications’ education and
  training among radiographers is the leading cause of poor utilization, perception, and
  knowledge globally. Equally, Ayorinde et al. (2024) allude that a lack of understanding of
  inputs and algorithms for AI and AI outputs among healthcare workers contributes to low
  radiographers' perception and utilization of AI. Radiographers should fully understand the
  benefits and risks of AI to be able to make informed choices about its integration into
  radiography practices. The negative perceptions of a significant section of radiographers
  toward AI are compounded by their suspicion that it might take or substitute their jobs
  (Stogiannos et al., 2025).
</p>
<p>
  According to Sezgin (2023), AI is complementing radiographers by enhancing
  their skills rather than replacing them, leading to a paradigm shift in healthcare.
  As AI becomes an essential component of modern healthcare, organizations must
  invest in the necessary infrastructure, training, resources, and partnerships to
  facilitate its successful adoption and ensure equitable access for all.
</p>

<h3>Ethical Considerations in AI Use in Medical Radiography, Imaging, and Radiotherapy</h3>
<p>
  AI integration in radiography, medical imaging, and radiotherapy holds great
  promise by enhancing, not replacing, radiographers. However, its adoption must
  be guided by strong ethical principles, including transparency, accountability,
  patient safety, data privacy, and equitable access (Sezgin, 2023). Furthermore,
  according to Davenport and Kalakota (2019), as smart machines begin to assist in
  clinical decision-making, a range of ethical implications must be carefully considered.
</p>
<p>
  These include concerns around accountability for decisions made or influenced by AI,
  the transparency of algorithms and processes, the need for informed consent when AI
  tools are involved in patient care, and the protection of patient privacy and data security.
  Shinners et al. (2019) found that a lack of trust in AI delivering healthcare and
  improving patient outcomes among a section of healthcare practitioners also
  contributed to a negative perception of AI. Furthermore, Akudjedu et al. (2023)
  found that the lack of or poor AI regulatory and governance framework
  and alignment across different countries or geopolitical settings has affected full
  utilization or uptake of AI applications among professionals like radiographers.
</p>
<p>
  According to Stogiannos et al. (2025), radiographers in Europe have not yet fully
  embraced AI integration in their practice. However, with increasing knowledge and
  training, the perception that AI will replace their roles is gradually diminishing.
  The fear of the unknown among radiographers has contributed to a slower-than-expected
  adoption of AI. Additionally, Ayorinde et al. (2024) note that the integration of AI
  in radiography faces challenges related to the implementation of innovations. A study by
  Mohammad et al. (2024) indicated that although there is generally a positive
  attitude among radiographers and radiologists toward learning AI and its
  integration into practice, there are barriers such as a lack of training in AI
  and exposure to resources, which is the greatest setback to radiology AI integration.
  The UK radiographers, according to Rainey et al. (2024), expressed mixed feelings
  about AI in radiography practice, with some feeling that AI will kill the
  profession, while others feel AI brings better professional prospects and synergies.
</p>
<p>
  This calls for ongoing ethical oversight, institutional governance, and a commitment
  to uphold professional standards in the face of rapid technological advancement.
</p>

<h3>Foundational Truth</h3>
<p>
  The development of AI in healthcare relies heavily on vast amounts of validated, real-world
  patient data, which must be treated as foundational truth for algorithm training
  (Brady; Davenport & Kalakota, 2019). However, this process raises significant
  ethical concerns, particularly around patient confidentiality and data security.
</p>
<p>
  Furthermore, there is a risk of algorithmic bias when AI systems developed in one
  context based on specific factors such as race, gender, environment, or disease
  patterns are used in a different setting without proper adaptation. This can lead to
  unfair decisions, resulting in unequal treatment and potential harm to certain
  groups of patients (Geis et al., 2019). To ethically harness AI's potential, healthcare
  must prioritize transparency, accountability, and the protection of human rights, while
  resisting the misuse of radiological data for unethical or purely financial purposes.
</p>
<p>
  According to Geis et al. (2019), much of AI operates in a "black box," making it
  essential to ensure interpretability (the ability to understand how AI systems reach
  decisions), explainability (the ability to communicate these decisions to non-experts),
  and transparency (the ability for third parties to review and understand the
  decision-making process).
</p>
<p>
  Addressing these ethical challenges is essential to ensure that the integration of
  AI in healthcare upholds trust, equity, and professional integrity. Ensuring that AI
  systems are used responsibly requires clear guidelines to protect patient rights
  and uphold ethical standards in clinical practice. To ensure responsible
  integration of AI, healthcare organizations and professionals must
  invest in proper infrastructure, training, and oversight, prioritizing human dignity
  and ethical standards in all AI-supported care.
</p>

<h3>AI Ethical Considerations in Radiography and Radiotherapy</h3>

<h4>Beneficence (Do-no-harm)</h4>
<p>
  The ethical integration of AI in healthcare, particularly in radiography,
  imaging, and radiotherapy, must be grounded in core principles such as
  respecting human rights and freedoms, ensuring transparency and accountability,
  and maintaining human control and responsibility over clinical decisions
  (Varkey, 2020). As AI systems inevitably impact diagnosis and treatment, it
  becomes essential to define clear accountability frameworks for errors or
  unintended consequences, ensuring that responsibility is not obscured by
  technological complexity.
</p>
<p>
  The radiographers’ goal should be to maximize value through the ethical use of
  AI, prioritizing patient welfare and clinical integrity while resisting the lure of
  financial gain from unethical exploitation of data or AI tools (Geis et al., 2019).
  The Code of Conduct for Radiographers emphasizes the importance of
  compassion, professionalism, and ethical conduct in patient care (Health and Care
  Professions Council (HCPC), 2016). These human qualities, respect, dignity, empathy,
  effective communication, and professionalism, are essential in healthcare and cannot be
  replaced by AI. Radiographers play a crucial role in both diagnosing and
  supporting patients throughout their care journey, ensuring trust and comfort
  (Varkey, 2020).
</p>

<h3>Regulatory frameworks, guidelines, and policies on AI use</h3>
<p>
  The Society of Radiography in Kenya (SORK) has developed various guidelines and
  manuals to support the professional interests of radiographers in Kenya. These
  resources include the SORK Constitution, the Radiographers Act No. 28 of 2022, and
  other policy documents that provide a framework for the practice of radiography
  in Kenya (www.sork.org.ke). Additionally, the Kenya National AI Strategy 2025
  emphasizes the importance of creating unified legal frameworks and ethical
  guidelines to guide AI development and ensure governance and regulatory
  frameworks remain agile to accommodate evolving technologies (ICT Authority).
</p>
<p>
  These efforts highlight the need for comprehensive regulatory frameworks,
  guidelines, and policies to support the integration of AI in radiography and
  imaging, ensuring responsible development and deployment of AI technologies.
  Radiographers have an ethical duty to understand the clinical validity of
  datasets used to develop AI algorithms and how these algorithms process data in
  clinical settings. They must also ensure that the data reflects the patient
  population accurately, as biases in the data can negatively affect patient care.
</p>

<h3>Ethics of data ownership and privacy</h3>
<p>
  Handling AI data in healthcare is complex internationally, as different countries
  balance personal rights and collective social welfare in varying ways (Geis et al.,
  2019). While radiology and radiotherapy departments typically own the imaging
  and treatment data, patients still retain the legal right to a copy of their data and
  maintain ownership and control over their personal and sensitive information,
  including both medical and non-medical data.
</p>
<p>
  Therefore, explicit patient consent is required for sharing or using this data
  to develop AI algorithms. Exploitation, mining, and misuse of patients' data for
  financial gain without consent borders unethical conduct (Davenport & Kalakota,
  2019). Radiographers must ensure that patients' data is consented to before it is
  used to develop AI algorithms.
</p>

<h3>Lack of Empathy</h3>
<p>
  The Code of Conduct for Radiographers emphasizes the importance of
  compassion, professionalism, and ethical conduct in patient care. Radiographers
  are expected to prioritize patient well-being, communicate clearly, and offer
  emotional support, especially when delivering life-changing news. These human
  qualities cannot be replicated by AI.
</p>
<p>
  Radiographers need appropriate training to confidently lead in AI-driven clinical
  transformation, enhance patient care, and contribute to research and innovation in
  imaging and radiotherapy services. The relevant line ministry, health
  regulators, and professional associations such as the Society of Radiography in
  Kenya (SORK), in consultation with experts and technology drivers, need to integrate
  the regulatory frameworks, guidelines, and policies to support AI in radiography
  and imaging.
</p>
<p>
  These frameworks should ensure responsible development and
  deployment of AI, focusing on accountability, transparency, fairness,
  and patient rights, while minimizing biases and improving patient care
  through strict oversight and governance.
</p>

<h3>Conclusion</h3>
<p>
  AI is set to significantly impact radiography and radiotherapy, with
  radiographers playing a key role in integrating AI into their clinical practice.
  While AI will not replace radiographers, it will augment their work, particularly in
  enhancing efficiency, effectiveness, quality, and standardized imaging,
  precision, and help in triaging, ultimately reducing turnaround times and improving
  overall patient care experience.
</p>
<p>
  Despite current uncertainty among radiographers about AI’s impact on careers and daily
  practice, especially in LMICs, studies have shown that useful deployment of AI
  transforms the radiographers' work, and hence there is a need to embrace and celebrate
  the technology. However, for successful adoption, AI must be regulated,
  integrated into systems, and supported by targeted education. Radiographers need
  appropriate training to confidently lead in AI-driven clinical transformation, enhance
  patient care, and contribute to research and innovation in imaging and
  radiotherapy services.
</p>
<p>
  Author: Jevas Kenyanya<br>
  President Society of Radiography in Kenya (SORK)
</p>
        """
    },
    {
        "title": "The Evolution Landscape of Radiology: Current Trends and Future Prospects",
        "summary": "An expert review of radiology's evolution, examining current trends in diagnostic imaging and exploring the innovative technologies shaping the future of patient care.",
        "author": "Dr. Tima Nassir Ali Khamis",
        "author_bio": "Radiologist and researcher dedicated to advancing diagnostic imaging practices and technology integration in African healthcare.",
        "author_image": None,
        "author_linkedin": None,
        "author_twitter": None,
        "author_facebook": None,
        "author_whatsapp": None,
        "author_email": "editor@insideimaging.example",
        "author_website": None,
        "date": "July 2025",
        "read_time": "12 min read",
        "url": "/magazine#page=41",
        "author_qualifications": "Consultant Radiologist. HOD-Radiology Department; C.G.T.R.H.",
        "content": """
<h3>Introduction</h3>

<h3>Current Trends in Radiology</h3>
<p>
  Radiology is a cornerstone of modern healthcare, offering crucial diagnostic and therapeutic
  insights through imaging technologies such as X-ray, ultrasound, computed tomography (CT),
  magnetic resonance imaging (MRI), and nuclear medicine. Since Wilhelm Roentgen’s discovery
  of X-rays in 1895, radiology has continuously evolved, integrating technological
  advancements to enhance disease detection, treatment planning, and patient outcomes
  (Brady et al., 2020).
</p>
<p>
  Advancements in radiology contribute to improved diagnostic accuracy, reduced invasive
  procedures, and optimized treatment strategies. Innovations such as artificial intelligence
  (AI), hybrid imaging, and high-resolution modalities have revolutionized the field. However,
  radiology faces challenges, particularly in low-resource settings where cost, infrastructure,
  and workforce limitations hinder accessibility. This paper explores the current trends
  shaping radiology, key challenges, and the future of radiology in Kenya, concluding with
  recommendations for stakeholders to enhance imaging services.
</p>

<h3>Hybrid Imaging Modalities</h3>
<p>
  Hybrid imaging combines two or more imaging techniques to improve diagnostic accuracy.
  The integration of positron emission tomography (PET) with CT (PET/CT) or MRI (PET/MRI)
  has significantly enhanced oncologic imaging, enabling precise tumor localization and
  metabolic assessment. Similarly, single-photon emission computed tomography (SPECT/CT)
  has improved the detection of musculoskeletal and cardiovascular conditions (Kjaer et al.,
  2017). Hybrid imaging is particularly valuable in oncology, neurology, and cardiology, where
  multimodal assessment provides comprehensive disease characterization.
</p>

<h3>Artificial Intelligence (AI) in Radiology</h3>
<p>
  AI has emerged as a transformative force in radiology, improving imaging interpretation,
  workflow automation, and predictive analytics. AI-powered algorithms assist radiologists in
  detecting abnormalities, reducing diagnostic errors, and expediting image analysis. Deep
  learning models, such as convolutional neural networks (CNNs), have demonstrated high
  accuracy in detecting lung nodules, breast tumors, and brain lesions (Lakhani &amp; Sundaram,
  2017). Additionally, AI applications streamline radiology workflows by automating report
  generation and prioritizing critical cases, enhancing efficiency and reducing workload (Hosny
  et al., 2018).
</p>

<h3>Advances in MRI and CT Technologies</h3>
<p>
  MRI and CT technologies have seen substantial improvements in speed, resolution, and
  functional imaging capabilities. Ultra-high-field MRI (7 Tesla and above) offers superior soft
  tissue contrast and neuroimaging capabilities, enabling early detection of neurological
  disorders (Ladd et al., 2018). Spectral CT imaging, including dual-energy CT, enhances tissue
  characterization by differentiating materials based on atomic composition. Moreover,
  low-dose CT protocols and iterative reconstruction techniques minimize radiation exposure
  while maintaining image quality, addressing safety concerns associated with ionizing radiation
  (Brenner &amp; Hall, 2007).
</p>

<h3>Teleradiology and Remote Imaging</h3>
<p>
  Teleradiology has become increasingly relevant, particularly in regions with a shortage of
  radiologists. Digital transmission of medical images allows radiologists to interpret scans
  remotely, bridging the gap in radiology services between urban and rural areas. Cloud-based
  radiology platforms and picture archiving and communication systems (PACS) facilitate
  seamless image sharing and collaboration among healthcare providers, improving access to
  expert opinions (Shan et al., 2020).
</p>

<h3>Challenges in Radiology</h3>
<p>
  Despite technological advancements, several challenges persist in radiology, particularly in
  resource-limited settings.
</p>

<h4>High Costs and Limited Accessibility</h4>
<p>
  Advanced imaging modalities, such as MRI and PET/CT, require substantial capital
  investment, making them inaccessible in many low- and middle-income countries (LMICs).
  The cost of imaging equipment, maintenance, and consumables often limits the availability of
  radiological services, particularly in rural healthcare facilities (Kawooya, 2012). Additionally,
  the cost of imaging examinations may be prohibitive for many patients, exacerbating
  healthcare disparities.
</p>

<h4>Workforce Shortages and Training Gaps</h4>
<p>
  The global shortage of radiologists remains a significant challenge, particularly in Africa.
  Many developing countries have a low radiologist-to-population ratio, leading to delays in
  imaging interpretation and diagnosis (Morris et al., 2019). Moreover, there are training gaps
  in emerging technologies, such as AI-assisted radiology and hybrid imaging, necessitating
  continuous professional development for radiologists and radiographers.
</p>

<h4>Policy and Regulatory Issues</h4>
<p>
  The integration of AI in radiology raises ethical and regulatory concerns regarding data
  privacy, liability, and algorithm bias. The lack of standardized guidelines for AI
  implementation in radiology poses challenges in ensuring the safety and accuracy of
  AI-driven diagnoses (Langlotz, 2019). Additionally, in many developing countries, limited
  government investment in radiology infrastructure and workforce development hinders the
  expansion of imaging services.
</p>

<h4>Radiation Safety Concerns</h4>
<p>
  The increasing use of ionizing radiation in diagnostic imaging raises concerns about
  radiation exposure, particularly for pediatric and pregnant patients. Efforts to optimize
  imaging protocols and implement dose-reduction techniques are crucial to minimizing
  radiation-related risks while maintaining diagnostic accuracy (Smith-Bindman et al., 2012).
</p>

<h3>The Future of Radiology in Kenya</h3>

<h4>Expansion of Imaging Infrastructure</h4>
<p>
  Expanding imaging infrastructure, particularly in county and sub-county hospitals, will
  improve access to diagnostic services. Government and private sector investments in MRI,
  CT, and ultrasound equipment are essential for addressing disparities in imaging
  availability. Public-private partnerships (PPPs) can facilitate the acquisition of advanced
  imaging technology and ensure sustainable radiology services (Okeji et al., 2021).
</p>

<h4>AI Integration and Digital Health Solutions</h4>
<p>
  Kenya has the potential to leverage AI and digital health solutions to enhance radiology
  services. AI-driven diagnostic tools can assist radiologists in interpreting scans more
  efficiently, reducing diagnostic delays. Additionally, mobile health (mHealth) applications
  and telemedicine platforms can improve radiology access in remote areas, enabling timely
  diagnosis and treatment (Mwachaka et al., 2021).
</p>

<h4>Strengthening Radiology Training and Capacity Building</h4>
<p>
  To address the shortage of radiologists, Kenya must strengthen radiology training programs
  and expand opportunities for specialization. Collaborations between local medical schools
  and international radiology institutions can facilitate knowledge exchange and skill
  development. Incorporating AI and hybrid imaging training into radiology curricula will
  prepare future radiologists for emerging trends in medical imaging.
</p>

<h4>Policy and Regulatory Reforms</h4>
<p>
  Kenyan policymakers should develop and implement regulations that govern AI use in
  radiology, ensuring ethical and legal compliance. Establishing national imaging guidelines
  and radiation safety protocols will standardize imaging practices across healthcare
  facilities. Additionally, expanding insurance coverage for radiological procedures will
  improve affordability and access to imaging services.
</p>

<h3>Conclusion and Call for Action</h3>
<p>
  The evolution of radiology has transformed medical diagnosis and treatment, with
  advancements in AI, hybrid imaging, and MRI/CT technologies enhancing diagnostic
  accuracy and efficiency. However, challenges such as high costs, workforce shortages, and
  policy gaps hinder optimal radiology service delivery, particularly in resource-limited
  settings like Kenya.
</p>
<p>To improve radiology services in Kenya, stakeholders should:</p>
<ul>
  <li>Expand imaging infrastructure through government and private sector investments.</li>
  <li>Integrate AI and digital health solutions to optimize radiology workflows and access.</li>
  <li>Enhance radiology training programs to address workforce shortages and skill gaps.</li>
  <li>Develop regulatory frameworks to govern AI implementation and radiation safety.</li>
  <li>Increase funding and insurance coverage for diagnostic imaging services.</li>
</ul>
<p>
  By addressing these challenges and embracing technological innovations, Kenya can advance
  its radiology sector, ultimately improving healthcare outcomes for its population.
</p>

<details>
  <summary>References (click to expand)</summary>
  <ul>
    <li>
      Brady, A. P., Bello, J. A., Derchi, L. E., Fuchsjäger, M., Krestin, G. P., Brink, J. A., 
      &amp; Vanhoenacker, P. (2020). Radiology in the era of AI: Where are we now? 
      <em>Insights into Imaging, 11</em>(1), 1–20. https://doi.org/10.1186/s13244-020-00887-6
    </li>
    <li>
      Brenner, D. J., &amp; Hall, E. J. (2007). Computed tomography: An increasing source of
      radiation exposure. <em>New England Journal of Medicine, 357</em>(22), 2277–2284.
      https://doi.org/10.1056/NEJMra072149
    </li>
    <li>
      Hosny, A., Parmar, C., Quackenbush, J., Schwartz, L. H., &amp; Aerts, H. J. (2018).
      Artificial intelligence in radiology. <em>Nature Reviews Cancer, 18</em>(8), 500–510.
      https://doi.org/10.1038/s41568-018-0016-5
    </li>
    <li>
      Kawooya, M. G. (2012). Training for rural radiology and imaging in sub-Saharan Africa:
      Addressing the mismatch between services and population. <em>Journal of Clinical Imaging
      Science, 2</em>, 37. https://doi.org/10.4103/2156-7514.99157
    </li>
    <li>
      Kjaer, A., Hasbak, P., &amp; Hesse, B. (2017). Hybrid imaging in cardiovascular medicine:
      PET/MR and PET/CT. <em>Heart, 103</em>(12), 957–968.
      https://doi.org/10.1136/heartjnl-2016-310162
    </li>
    <li>
      Ladd, M. E., Bachert, P., Meyerspeer, M., Moser, E., Nagel, A. M., Norris, D. G., 
      &amp; Zaitsev, M. (2018). Pros and cons of ultra-high-field MRI/MRS for human application.
      <em>Progress in Nuclear Magnetic Resonance Spectroscopy, 109</em>, 1–50.
      https://doi.org/10.1016/j.pnmrs.2018.06.001
    </li>
    <li>
      Lakhani, P., &amp; Sundaram, B. (2017). Deep learning at chest radiography:
      Automated classification of pulmonary tuberculosis by using convolutional neural networks.
      <em>Radiology, 284</em>(2), 574–582.
    </li>
    <li>
      Langlotz, C. P. (2019). Will artificial intelligence replace radiologists?
      <em>Radiology: Artificial Intelligence, 1</em>(3), e190058.
    </li>
    <li>
      Morris, E., Feigin, D., &amp; Myers, L. (2019). The global radiologist shortage: The South
      African perspective. <em>The South African Radiographer, 57</em>(2), 10–15.
    </li>
    <li>
      Mwachaka, P. M., Mbugua, P., &amp; Musau, P. (2021). The role of artificial intelligence in
      radiology in Kenya: Current status and future prospects. <em>East African Medical Journal,
      98</em>(10), 451–459.
    </li>
    <li>
      Okeji, M. C., Nwobi, I. C., &amp; Agwuna, K. K. (2021). Expanding radiology services in Africa:
      Challenges and prospects. <em>Radiography, 27</em>(3), 625–631.
    </li>
    <li>
      Shan, H., Padole, A., Homayounieh, F., Kruger, U., Khera, R. D., Enzmann, D. R., 
      &amp; Kalra, M. K. (2020). Competitive performance of a modularized deep learning model versus
      commercial algorithms for liver and lung lesion detection. <em>Nature Communications,
      11</em>(1), 1–13.
    </li>
    <li>
      Smith-Bindman, R., Lipson, J., Marcus, R., Kim, K. P., Mahesh, M., Gould, R., 
      &amp; Miglioretti, D. L. (2012). Radiation dose associated with common computed tomography
      examinations and the associated lifetime attributable risk of cancer. 
      <em>Archives of Internal Medicine, 169</em>(22), 2078–2086.
    </li>
  </ul>
</details>

<h3>Author</h3>
<p><strong>Author:</strong> Dr. Tima Nassir Ali Khamis</p>
<p>
  She is a Consultant Radiologist and Head of the Radiology Department at Coast General
  Teaching and Referral Hospital in Mombasa, Kenya. With extensive experience in diagnostic
  imaging, including CT, MRI, X-rays, and ultrasound, she is also skilled in image-guided
  procedures. She serves as a part-time lecturer at the Technical University of Mombasa,
  has a strong research background with published work on pediatric radiation doses,
  and actively participates in national and international radiology conferences. Her key
  interests include nuclear imaging and oncologic imaging.
</p>
        """
    },
]

MARQUEE_IMAGES = [
    # Real radiology examples from the team
    "/static/images/marquee/IMG-20251030-WA0002.jpg",
    "/static/images/marquee/IMG-20251030-WA0003.jpg",
    "/static/images/marquee/IMG-20251030-WA0004.jpg",
    "/static/images/marquee/IMG-20251030-WA0005.jpg",
    "/static/images/marquee/IMG-20251030-WA0006.jpg",
    "/static/images/marquee/IMG-20251030-WA0007.jpg",
    "/static/images/marquee/IMG-20251030-WA0008.jpg",
    "/static/images/marquee/IMG-20251030-WA0009.jpg",
    "/static/images/marquee/IMG-20251030-WA0010.jpg",
    "/static/images/marquee/IMG-20251030-WA0011.jpg",
    "/static/images/marquee/IMG-20251030-WA0012.jpg",
    "/static/images/marquee/IMG-20251030-WA0013.jpg",
    "/static/images/marquee/IMG-20251030-WA0014.jpg",
    "/static/images/marquee/IMG-20251030-WA0015.jpg",
    "/static/images/marquee/IMG-20251030-WA0016.jpg",
    "/static/images/marquee/IMG-20251030-WA0017.jpg",
    "/static/images/marquee/IMG-20251030-WA0018.jpg",
    "/static/images/marquee/IMG-20251030-WA0019.jpg",
    "/static/images/marquee/IMG-20251030-WA0020.jpg",
]

# Initialize database
try:
    db.init_db()
except Exception:
    logging.exception("Database initialization failed")

# --- translate wiring ---
try:
    from src.translate import Glossary, build_structured  # type: ignore
except Exception:
    logging.exception("translate import failed")
    Glossary = None  # type: ignore

    def build_structured(report_text: str, glossary=None, language: str = "English"):
        return {
            "reason": "",
            "technique": "",
            "findings": (report_text or "").strip(),
            "conclusion": "",
            "concern": "",
        }

# try to load a glossary if you have one; otherwise None is fine
LAY_GLOSS = None
try:
    if Glossary:
        gloss_path = os.path.join(os.path.dirname(__file__), "data", "glossary.csv")
        if os.path.exists(gloss_path):
            LAY_GLOSS = Glossary.load(gloss_path)
except Exception:
    logging.exception("glossary load failed")
    LAY_GLOSS = None

# PDF engine
try:
    from weasyprint import HTML  # type: ignore
except Exception:
    HTML = None  # type: ignore


def _extract_text_from_pdf_bytes(data: bytes) -> str:
    """Robust PDF text extraction using pdfminer.six."""
    try:
        from pdfminer.high_level import extract_text  # type: ignore
    except Exception:
        logging.exception("pdfminer.six not available")
        return ""
    try:
        return extract_text(io.BytesIO(data)) or ""
    except Exception:
        logging.exception("pdfminer extract_text failed")
        return ""


def _extract_text_from_image_bytes(data: bytes) -> str:
    """Extract text from images (JPEG/PNG).

    Works best for phone photos. Max 5 MB for Bytes input.
    """
    if len(data) > 5 * 1024 * 1024:
        logging.warning("Image >5MB; Textract DetectDocumentText requires <=5MB for Bytes.")
        return ""

    try:
        resp = _textract().detect_document_text(Document={"Bytes": data})
    except Exception:
        logging.exception("Textract DetectDocumentText failed")
        return ""

    # Pull out LINE blocks in natural reading order
    lines = []
    for block in resp.get("Blocks", []):
        if block.get("BlockType") == "LINE" and block.get("Text"):
            lines.append(block["Text"].strip())

    # Fallback: if no LINEs, try WORDs
    if not lines:
        words = [b.get("Text", "").strip() for b in resp.get("Blocks", []) if b.get("BlockType") == "WORD"]
        lines = [" ".join(w for w in words if w)]

    text = "\n".join(l for l in lines if l)
    return text.strip()


def _extract_text_from_docx_bytes(data: bytes) -> str:
    """Extract text from a DOCX file."""
    try:
        from docx import Document  # type: ignore
    except Exception:
        logging.exception("python-docx not available")
        return ""
    
    try:
        doc = Document(io.BytesIO(data))
        paragraphs = []
        for para in doc.paragraphs:
            if para.text.strip():
                paragraphs.append(para.text.strip())
        
        # Also extract text from tables
        for table in doc.tables:
            for row in table.rows:
                for cell in row.cells:
                    if cell.text.strip():
                        paragraphs.append(cell.text.strip())
        
        return "\n".join(paragraphs)
    except Exception:
        logging.exception("docx extraction failed")
        return ""


def _extract_text_from_heif_bytes(data: bytes) -> str:
    """
    Extract text from HEIF/HEIC images (iOS photos) by converting to JPEG
    and then using AWS Textract.
    """
    try:
        import pillow_heif  # type: ignore
        from PIL import Image  # type: ignore
        pillow_heif.register_heif_opener()
    except Exception:
        logging.exception("pillow-heif not available")
        return ""
    
    try:
        # Convert HEIF to JPEG in memory
        heif_image = pillow_heif.read_heif(io.BytesIO(data))
        image = Image.frombytes(
            heif_image.mode, 
            heif_image.size, 
            heif_image.data,
            "raw"
        )
        
        # Convert to JPEG bytes
        jpeg_buffer = io.BytesIO()
        image.save(jpeg_buffer, format="JPEG", quality=95)
        jpeg_bytes = jpeg_buffer.getvalue()
        
        # Use existing image extraction with Textract
        return _extract_text_from_image_bytes(jpeg_bytes)
    except Exception:
        logging.exception("HEIF extraction failed")
        return ""




def _pdf_response_from_html(html_str: str, *, filename="inside-imaging-report.pdf", inline: bool = False):
    if not HTML:
        raise RuntimeError("WeasyPrint is not installed or failed to import")
    # host_url lets WeasyPrint resolve /static and relative asset URLs
    pdf_bytes = HTML(string=html_str, base_url=request.host_url).write_pdf()
    resp = make_response(pdf_bytes)
    resp.headers["Content-Type"] = "application/pdf"
    disp = "inline" if inline else "attachment"
    resp.headers["Content-Disposition"] = f'{disp}; filename="{filename}"'
    return resp


def _parse_brain_lesion(structured: dict) -> dict:
    """Parse brain lesion location and size from conclusion/findings text."""
    import re
    
    conclusion = (structured.get("conclusion") or "").lower()
    findings = (structured.get("findings") or "").lower()
    # Strip HTML tags
    conclusion = re.sub(r'<[^>]+>', ' ', conclusion)
    findings = re.sub(r'<[^>]+>', ' ', findings)
    combined_text = conclusion + ' ' + findings
    
    # Location mapping: [axial_x, axial_y, sagittal_x, sagittal_y, coronal_x, coronal_y]
    location_map = {
        'right frontoparietal': [145, 95, 135, 90, 155, 85],
        'left frontoparietal': [95, 95, 135, 90, 85, 85],
        'right frontal': [140, 85, 125, 75, 150, 75],
        'left frontal': [100, 85, 125, 75, 90, 75],
        'right parietal': [150, 100, 140, 95, 160, 90],
        'left parietal': [90, 100, 140, 95, 80, 90],
        'right temporal': [155, 115, 145, 110, 165, 105],
        'left temporal': [85, 115, 145, 110, 75, 105],
        'right occipital': [155, 125, 155, 130, 165, 120],
        'left occipital': [85, 125, 155, 130, 75, 120],
        'sphenoid wing': [130, 105, 120, 100, 135, 100],
        'greater sphenoid wing': [135, 105, 120, 100, 140, 100],
        'cerebellum': [120, 145, 80, 165, 120, 165],
        'brainstem': [120, 155, 90, 175, 120, 175],
        'thalamus': [120, 110, 115, 110, 120, 110],
        'basal ganglia': [115, 110, 115, 105, 115, 105]
    }
    
    # Parse size (e.g., "5.4 x 5.6 x 6.7 cm" or "measures 2.5 cm")
    size_match = re.search(r'(\d+\.?\d*)\s*x\s*(\d+\.?\d*)\s*x\s*(\d+\.?\d*)\s*cm|measures?\s+(\d+\.?\d*)\s*cm', combined_text, re.IGNORECASE)
    avg_size = 18  # default radius
    if size_match:
        if size_match.group(1):
            dims = [float(size_match.group(1)), float(size_match.group(2)), float(size_match.group(3))]
            avg_size = min(30, max(10, sum(dims) / 3 * 3))  # scale to pixels
        elif size_match.group(4):
            avg_size = min(30, max(10, float(size_match.group(4)) * 3))
    
    # Find best location match
    best_match = None
    best_length = 0
    for loc in location_map:
        if loc in combined_text and len(loc) > best_length:
            best_match = loc
            best_length = len(loc)
    
    default_coords = [145, 95, 135, 90, 155, 85]
    return {
        'location': best_match or 'right frontoparietal',
        'coords': location_map.get(best_match) if best_match else default_coords,
        'size': int(avg_size),
        'found': best_match is not None
    }


_TRIAGE_SECTION_RX = re.compile(
    r"(?im)^\s*(findings|impression|conclusion|technique|history|clinical\s+history|"
    r"indication|comparison|procedure|exam(?:ination)?|study|details)\s*[:\-]"
)
_TRIAGE_MODALITY_TOKENS = [
    "ct", "mri", "x-ray", "xray", "ultrasound", "pet", "spect", "angiogram",
    "fluoroscopy", "mammo", "mammogram", "cect", "mra", "cta", "doppler",
]
_TRIAGE_IMAGING_TERMS = [
    "lesion", "mass", "nodule", "enhancement", "attenuation", "hyperdense",
    "hypodense", "hyperintense", "hypointense", "density", "signal", "axial",
    "sagittal", "coronal", "sequence", "cm", "mm", "vertebra", "lobar",
    "hepatic", "renal", "ventricle", "parenchyma", "impression", "findings",
    "technique", "study", "comparison", "contrast",
]
_TRIAGE_NEGATIVE_TOKENS = [
    "syllabus", "semester", "homework", "assignment", "professor", "student",
    "lecture", "quiz", "final exam", "midterm", "credit hours", "office hours",
    "course objectives", "course description", "grading policy", "title ix",
    "canvas site", "attendance policy",
]


def _triage_radiology_report(text: str) -> tuple[bool, dict]:
    """Quick heuristic to reject non-radiology uploads before hitting the LLM."""

    sample = (text or "").strip()
    if not sample:
        return False, {"reason": "empty"}

    snippet = sample[:20000]
    lower = snippet.lower()

    # Basic counts
    words = re.findall(r"\b\w+\b", snippet)
    word_count = len(words)
    section_hits = {match.group(1).lower() for match in _TRIAGE_SECTION_RX.finditer(snippet)}
    modality_hits = [token for token in _TRIAGE_MODALITY_TOKENS if token in lower]
    imaging_hits = [token for token in _TRIAGE_IMAGING_TERMS if token in lower]
    measurement_count = len(re.findall(r"\b\d+(?:\.\d+)?\s*(?:mm|cm)\b", lower))
    negative_hits = [token for token in _TRIAGE_NEGATIVE_TOKENS if token in lower]

    # Legacy keyword heuristics to preserve prior thresholds
    radiology_keywords = [
        "radiology", "radiologist", "imaging", "scan", "ct", "mri", "x-ray", "xray",
        "ultrasound", "pet", "findings", "impression", "technique", "contrast",
        "examination", "study", "patient", "indication", "conclusion", "comparison",
    ]
    anatomy_terms = [
        "brain", "lung", "liver", "kidney", "heart", "spine", "abdomen", "pelvis",
        "chest", "thorax", "head", "skull", "bone", "soft tissue", "vessel", "artery",
        "vein", "organ", "lesion", "mass", "nodule",
    ]
    radiology_keyword_count = sum(1 for keyword in radiology_keywords if keyword in lower)
    anatomy_count = sum(1 for term in anatomy_terms if term in lower)

    score = 0
    if word_count >= 90:
        score += 1
    if len(section_hits) >= 2:
        score += 2
    elif len(section_hits) == 1:
        score += 1
    if radiology_keyword_count >= 3:
        score += 1
    if anatomy_count >= 2 or len(imaging_hits) >= 4:
        score += 1
    if modality_hits:
        score += 2
    if measurement_count >= 3:
        score += 2
    elif measurement_count >= 1:
        score += 1
    if "impression" in section_hits:
        score += 1
    if "findings" in section_hits:
        score += 1

    diagnostics = {
        "word_count": word_count,
        "sections": sorted(section_hits),
        "modalities": modality_hits,
        "imaging_hits": imaging_hits[:10],
        "radiology_keyword_count": radiology_keyword_count,
        "anatomy_count": anatomy_count,
        "measurement_count": measurement_count,
        "negative_hits": negative_hits,
        "score": score,
    }

    # Hard rejection conditions
    if word_count < 80 and not (len(section_hits) >= 3 and modality_hits):
        diagnostics["reason"] = "too_short"
        return False, diagnostics
    if negative_hits and score < 6:
        diagnostics["reason"] = "non_medical_tokens"
        return False, diagnostics
    if not modality_hits and len(section_hits) < 2 and len(imaging_hits) < 5:
        diagnostics["reason"] = "insufficient_radiology_markers"
        return False, diagnostics
    if score < 5:
        diagnostics["reason"] = "low_confidence"
        return False, diagnostics

    diagnostics["reason"] = "ok"
    return True, diagnostics


def _extract_focus_details(raw_text: str, organ: str | None) -> dict:
    if not organ:
        return {}

    low = (raw_text or "").lower()
    focus: dict = {"organ": organ}

    if organ == 'lung':
        has_right = bool(re.search(r'\bright[^.,;]{0,40}(lung|lobe)', low))
        has_left = bool(re.search(r'\bleft[^.,;]{0,40}(lung|lobe)', low))
        has_bilateral = bool(re.search(r'\bbilateral\b|\bboth\s+lungs?\b|\ball\s+lobes\b', low))
        if has_bilateral or (has_right and has_left):
            focus['laterality'] = 'bilateral'
        elif has_right:
            focus['laterality'] = 'right'
        elif has_left:
            focus['laterality'] = 'left'

        if re.search(r'\b(apex|apical|upper\s+lobe|upper\s+zone|superior\s+segment)\b', low):
            focus['zone'] = 'upper'
        elif re.search(r'\bmiddle\s+lobe\b|\bmid\s+lobe\b|\bperihilar\b', low):
            focus['zone'] = 'middle'
        elif re.search(r'\b(lower\s+lobe|lower\s+zone|basal|base|inferior\s+segment)\b', low):
            focus['zone'] = 'lower'

    elif organ == 'kidney':
        has_right = bool(re.search(r'\bright[^.,;]{0,30}(kidney|renal)', low))
        has_left = bool(re.search(r'\bleft[^.,;]{0,30}(kidney|renal)', low))
        has_bilateral = bool(re.search(r'\bbilateral\b|\bboth\s+kidneys\b|\ball\s+renal\b', low))
        if has_bilateral or (has_right and has_left):
            focus['laterality'] = 'bilateral'
        elif has_right:
            focus['laterality'] = 'right'
        elif has_left:
            focus['laterality'] = 'left'

        if re.search(r'\bupper\s+pole\b|\bsuperior\s+pole\b', low):
            focus['zone'] = 'upper'
        elif re.search(r'\blower\s+pole\b|\binferior\s+pole\b', low):
            focus['zone'] = 'lower'
        elif re.search(r'\bmid(?:dle)?\s+pole\b|\binterpolar\b', low):
            focus['zone'] = 'mid'

    elif organ == 'liver':
        has_right = bool(re.search(r'\bright\s+(hepatic\s+)?lobe\b', low))
        has_left = bool(re.search(r'\bleft\s+(hepatic\s+)?lobe\b', low))
        has_bilateral = bool(re.search(r'\bboth\s+lobe\b|\bdiffuse\b|\bbilateral\b', low))
        if has_bilateral or (has_right and has_left):
            focus['laterality'] = 'bilateral'
        elif has_right:
            focus['laterality'] = 'right'
        elif has_left:
            focus['laterality'] = 'left'

        segment_hits = re.findall(r'\bsegment\s+([ivx]{1,4})\b', low)
        if segment_hits:
            segment_map = {
                'i': 'caudate',
                'ii': 'left', 'iii': 'left', 'iv': 'left', 'iva': 'left', 'ivb': 'left',
                'v': 'right', 'vi': 'right', 'vii': 'right', 'viii': 'right'
            }
            first = segment_hits[0]
            focus['segment'] = first.upper()
            zone = segment_map.get(first.lower())
            if zone:
                focus['segment_group'] = zone
                if zone in ('left', 'right') and 'laterality' not in focus:
                    focus['laterality'] = zone

    elif organ == 'spine':
        levels: set[str] = set()
        for token in re.findall(r'\b[cClLtTsS][0-9]{1,2}\b', low):
            levels.add(token.upper())
        for start, end in re.findall(r'\b([cClLtTsS][0-9]{1,2})\s*[-–to]+\s*([cClLtTsS]?[0-9]{1,2})\b', low):
            levels.add(start.upper())
            if end:
                prefix = end[0] if end and end[0].isalpha() else start[0]
                digits = end[1:] if end and end[0].isalpha() else end
                levels.add((prefix + digits).upper())
        if levels:
            order_map = {'C': 0, 'T': 1, 'L': 2, 'S': 3}
            focus['levels'] = sorted(levels, key=lambda lvl: (order_map.get(lvl[0], 4), int(re.sub(r'[^0-9]', '', lvl) or 0)))
            if any(lvl.startswith('L') for lvl in levels):
                focus['region'] = 'lumbar'
            elif any(lvl.startswith('T') for lvl in levels):
                focus['region'] = 'thoracic'
            elif any(lvl.startswith('C') for lvl in levels):
                focus['region'] = 'cervical'
            elif any(lvl.startswith('S') for lvl in levels):
                focus['region'] = 'sacral'

    elif organ == 'brain':
        if re.search(r'\bright[^.]{0,40}(frontal|parietal|temporal|occipital|hemisphere)', low):
            focus['laterality'] = 'right'
        elif re.search(r'\bleft[^.]{0,40}(frontal|parietal|temporal|occipital|hemisphere)', low):
            focus['laterality'] = 'left'

        for region_key, label in [
            ('frontal', 'frontal'),
            ('parietal', 'parietal'),
            ('temporal', 'temporal'),
            ('occipital', 'occipital'),
            ('cerebell', 'cerebellum'),
            ('brainstem', 'brainstem')
        ]:
            if region_key in low:
                focus.setdefault('regions', []).append(label)

        if 'regions' in focus:
            focus['regions'] = list(dict.fromkeys(focus['regions']))

    if len(focus) <= 1:
        return {}
    return focus


def _detect_abnormality_and_organ(structured: dict, patient: dict) -> dict:
    """
    Detect if report shows abnormalities and identify the affected organ.
    Returns: {'has_abnormality': bool, 'organ': str, 'abnormality_type': str}
    """
    import re
    
    conclusion = (structured.get("conclusion") or "").lower()
    findings = (structured.get("findings") or "").lower()
    study = (patient.get("study") or "").lower()
    
    # Strip HTML tags
    conclusion = re.sub(r'<[^>]+>', ' ', conclusion)
    findings = re.sub(r'<[^>]+>', ' ', findings)
    combined = conclusion + ' ' + findings + ' ' + study
    
    # Normal scan indicators
    normal_indicators = [
        r'\bnormal\b', r'\bunremarkable\b', r'\bno\s+abnormalit', r'\bwithin\s+normal\s+limits\b',
        r'\bno\s+significant\b', r'\bno\s+acute\b', r'\bclear\b.*\blungs?\b', r'\bintact\b'
    ]
    
    # Abnormality indicators
    abnormal_indicators = [
        r'\bmass\b', r'\btumou?r\b', r'\blesion\b', r'\bmeningioma\b', r'\bcancer\b',
        r'\bfracture\b', r'\bbleed\b', r'\bhemorrhage\b', r'\binfarct\b', r'\bstroke\b',
        r'\bedema\b', r'\bswelling\b', r'\bobstruction\b', r'\benlarged\b',
        r'\badenopathy\b', r'\bnodule\b', r'\bhydro\w+\b', r'\bherniation\b',
        r'\bshift\b', r'\bcompression\b', r'\beffusion\b', r'\bpneumonia\b'
    ]
    
    # Count indicators
    normal_count = sum(1 for pattern in normal_indicators if re.search(pattern, combined, re.I))
    abnormal_count = sum(1 for pattern in abnormal_indicators if re.search(pattern, combined, re.I))
    
    has_abnormality = abnormal_count > 0 and abnormal_count >= normal_count
    
    # Organ detection (order matters - more specific first)
    organ = None
    # Brain/head - but NOT "head of pancreas" or other anatomical heads
    if re.search(r'\b(brain|skull|cerebral|intracranial|cranial)\b', combined, re.I):
        organ = 'brain'
    elif re.search(r'\bhead\b', combined, re.I) and not re.search(r'\bhead\s+of\s+(pancreas|femur)\b', combined, re.I):
        organ = 'brain'
    elif re.search(r'\b(lung|pulmonary|chest|thorax|bronch)\b', combined, re.I):
        organ = 'lung'
    elif re.search(r'\b(liver|hepatic)\b', combined, re.I):
        organ = 'liver'
    elif re.search(r'\b(kidney|renal)\b', combined, re.I):
        organ = 'kidney'
    elif re.search(r'\b(spine|spinal|cervical|lumbar|thoracic|vertebra)\b', combined, re.I):
        organ = 'spine'
    elif re.search(r'\b(abdomen|abdominal|belly|pancreas|pancreatic)\b', combined, re.I):
        organ = 'abdomen'
    elif re.search(r'\b(pelvis|pelvic)\b', combined, re.I):
        organ = 'pelvis'
    
    # Abnormality type
    abnormality_type = None
    if has_abnormality:
        if re.search(r'\bmass\b|\btumou?r\b|\blesion\b|\bmeningioma\b|\bcancer\b', combined, re.I):
            abnormality_type = 'mass'
        elif re.search(r'\bfracture\b', combined, re.I):
            abnormality_type = 'fracture'
        elif re.search(r'\bbleed\b|\bhemorrhage\b', combined, re.I):
            abnormality_type = 'bleed'
        elif re.search(r'\bedema\b|\bswelling\b', combined, re.I):
            abnormality_type = 'edema'
        elif re.search(r'\binfection\b|\bpneumonia\b', combined, re.I):
            abnormality_type = 'infection'
        else:
            abnormality_type = 'other'
    
    focus = _extract_focus_details(combined, organ) if organ else {}

    return {
        'has_abnormality': has_abnormality,
        'organ': organ,
        'abnormality_type': abnormality_type,
        'focus': focus
    }


@app.route("/dashboard", methods=["GET"])
def dashboard():
    stats = db.get_stats()
    recent_reports = session.get("recent_reports", [])
    
    # Get user's persistent reports if logged in
    username = session.get("username")
    user_reports = []
    if username:
        try:
            user_reports = db.get_user_reports(username, limit=5)
        except Exception:
            logging.exception("Failed to fetch user reports")
    
    return render_template("index.html", stats=stats, languages=LANGUAGES, 
                          recent_reports=recent_reports, user_reports=user_reports)


@app.route("/upload", methods=["GET", "POST"])
def upload():
    if request.method == "GET":
        return redirect(url_for("dashboard"))

    file = request.files.get("file")
    lang = request.form.get("language", "English")
    file_text = request.form.get("file_text", "")
    context = request.form.get("context", "")
    extracted = ""
    src_kind = ""

    # Prefer pasted text if provided
    if file_text and file_text.strip():
        extracted = file_text.strip()
        src_kind = "text"
    elif file and file.filename:
        fname = secure_filename(file.filename)
        data = file.read()
        lower_name = fname.lower()
        try:
            if lower_name.endswith(".pdf"):
                extracted = _extract_text_from_pdf_bytes(data)
                src_kind = "pdf"
            elif lower_name.endswith((".heic", ".heif")):
                extracted = _extract_text_from_heif_bytes(data)
                src_kind = "heif"
                if not extracted:
                    flash(
                        "Unable to extract text from the HEIF/HEIC image. The file may be corrupted "
                        "or contain no readable text. Please try a different format or paste the text directly.",
                        "error",
                    )
                    return redirect(url_for("dashboard"))
            elif lower_name.endswith((".docx",)):
                extracted = _extract_text_from_docx_bytes(data)
                src_kind = "docx"
                if not extracted:
                    flash(
                        "Unable to extract text from the Word document. The file may be corrupted "
                        "or empty. Please try a different file or paste the text directly.",
                        "error",
                    )
                    return redirect(url_for("dashboard"))
            elif lower_name.endswith((".png", ".jpg", ".jpeg", ".webp", ".tif", ".tiff", ".bmp")):
                extracted = _extract_text_from_image_bytes(data)
                src_kind = "image"
                if not extracted:
                    flash(
                        "Unable to extract text from the image. The image may be too large (>5MB), "
                        "corrupted, or contain no readable text. Please try a clearer image or paste the text directly.",
                        "error",
                    )
                    return redirect(url_for("dashboard"))  # ✅ Fixed
            else:
                try:
                    extracted = data.decode("utf-8", "ignore")
                    src_kind = "text"
                except Exception:
                    logging.exception("decode failed; extracted empty")
        except Exception:
            logging.exception("file handling failed; extracted empty")

    logging.info("len(extracted)=%s kind=%s", len(extracted or ""), src_kind or "?")

    triage_ok, triage_diag = _triage_radiology_report(extracted)
    if not triage_ok:
        message = (
            "The uploaded file doesn't appear to be a radiology report. "
            "Please upload a full imaging report (with sections like Findings and Impression)."
        )
        flash(message, "error")
        logging.warning("Upload triage rejected: %s", triage_diag)
        return redirect(url_for("dashboard"))

    # Build structured summary
    try:
        logging.info("calling build_structured language=%s", lang)
        S = build_structured(extracted, LAY_GLOSS, language=lang) or {}
        logging.info(
            "summary_keys=%s",
            {k: len((S or {}).get(k) or "") for k in ("reason", "technique", "findings", "conclusion", "concern")},
        )
    except Exception:
        logging.exception("build_structured failed")
        S = {"reason": "", "technique": "", "findings": "", "conclusion": "", "concern": ""}

    # Patient and study from structured metadata
    patient_struct = S.get("patient") if isinstance(S, dict) else None
    if isinstance(patient_struct, dict) and patient_struct:
        patient = {
            "hospital": patient_struct.get("hospital", ""),
            "study": patient_struct.get("study", "Unknown"),
            "name": patient_struct.get("name", ""),
            "sex": patient_struct.get("sex", ""),
            "age": patient_struct.get("age", ""),
            "date": patient_struct.get("date", ""),
            "history": patient_struct.get("history", ""),
        }
    else:
        patient = {
            "hospital": S.get("hospital", ""),
            "study": S.get("study", "Unknown"),
            "name": S.get("name", ""),
            "sex": S.get("sex", ""),
            "age": S.get("age", ""),
            "date": S.get("date", ""),
            "history": "",
        }
    study = {"organ": patient.get("study") or "Unknown"}
    structured = S

    # Simple report stats for UI
    high_html = (S.get("findings", "") or "") + (S.get("conclusion", "") or "")
    report_stats = {
        "words": len((extracted or "").split()),
        "sentences": len(re.findall(r"[.!?]+", extracted or "")),
        "highlights_positive": high_html.count('class="ii-pos"'),
        "highlights_negative": high_html.count('class="ii-neg"'),
    }

    # Detect abnormality and organ for smart visualization
    diagnosis = _detect_abnormality_and_organ(structured, patient)

    # persist for later pages like /payment and PDF download
    session["structured"] = structured
    session["patient"] = patient
    session["language"] = lang
    session["diagnosis"] = diagnosis
    session["context"] = context

    report_id = None
    try:
        username = session.get("username", "")
        report_id = db.store_report_event(patient, structured, report_stats, lang, username, context)
    except Exception:
        logging.exception("Failed to persist report analytics.")

    if report_id:
        try:
            brief = db.get_report_brief(report_id)
        except Exception:
            logging.exception("Failed to fetch report brief.")
            brief = None
        if brief:
            history = session.get("recent_reports") or []
            filtered = [item for item in history if item.get("id") != report_id]
            session["recent_reports"] = [brief] + filtered[:4]

    # If context is provided, prepend it to the reason for scan
    if context:
        structured["reason"] = f"<strong>Patient context:</strong> {context}<br><br>" + (structured.get("reason") or "")
    return render_template(
        "result.html",
        S=structured,
        structured=structured,
        patient=patient,
        extracted=extracted,
        study=study,
        language=lang,
        report_stats=report_stats,
        diagnosis=diagnosis,
    )


@app.route("/reports/<int:report_id>")
def report_detail(report_id: int):
    record = db.get_report_detail(report_id)
    if not record:
        abort(404)

    structured = dict(record.get("structured") or {})
    patient = dict(record.get("patient") or {})
    language = record.get("language") or "English"

    findings_blob = (structured.get("findings") or "") + (structured.get("conclusion") or "")
    highlight_pos = findings_blob.count('class="ii-pos"')
    highlight_neg = findings_blob.count('class="ii-neg"')

    structured.setdefault("word_count", record.get("word_count", 0))
    structured.setdefault("sentence_count", 0)
    structured.setdefault("highlights_positive", highlight_pos)
    structured.setdefault("highlights_negative", highlight_neg)

    report_stats = {
        "words": structured.get("word_count", 0),
        "sentences": structured.get("sentence_count", 0),
        "highlights_positive": highlight_pos,
        "highlights_negative": highlight_neg,
    }

    session["structured"] = structured
    session["patient"] = patient
    session["language"] = language

    study = {"organ": patient.get("study") or "Unknown"}
    diagnosis = _detect_abnormality_and_organ(structured, patient)
    session["diagnosis"] = diagnosis

    return render_template(
        "result.html",
        S=structured,
        structured=structured,
        patient=patient,
        extracted="",
        study=study,
        language=language,
        report_stats=report_stats,
        diagnosis=diagnosis,
    )


@app.route("/download-pdf", methods=["GET", "POST"])
def download_pdf():
    try:
        if request.method == "POST":
            structured_raw = request.form.get("structured")
            patient_raw = request.form.get("patient")
            structured = json.loads(structured_raw) if structured_raw else session.get("structured", {}) or {}
            patient = json.loads(patient_raw) if patient_raw else session.get("patient", {}) or {}
        else:
            structured = session.get("structured", {}) or {}
            patient = session.get("patient", {}) or {}
    except Exception as e:
        logging.exception("Failed to parse form JSON")
        return jsonify({"error": "bad form JSON", "detail": str(e)}), 400

    # Detect abnormality and organ for conditional visualization
    diagnosis = _detect_abnormality_and_organ(structured, patient)
    
    # Parse brain lesion data for dynamic positioning (only if brain abnormality)
    lesion_data = None
    if diagnosis['has_abnormality'] and diagnosis['organ'] == 'brain':
        lesion_data = _parse_brain_lesion(structured)
    
    html_str = render_template("pdf_report.html", structured=structured, patient=patient, lesion_data=lesion_data, diagnosis=diagnosis)

    # hard fail if PDF fails. no HTML fallback.
    try:
        return _pdf_response_from_html(html_str, filename="inside-imaging-report.pdf", inline=False)
    except Exception as e:
        logging.exception("WeasyPrint PDF render failed")
        return jsonify({"error": "pdf_failed", "detail": str(e)}), 500


@app.get("/pdf-smoke")
def pdf_smoke():
    test_html = """
    <!doctype html><meta charset="utf-8">
    <style>@page{size:A4;margin:20mm} body{font-family:Arial}</style>
    <h1>WeasyPrint OK</h1><p>Static image test below.</p>
    <img src="/static/logo.png" alt="logo" height="24">
    """
    try:
        return _pdf_response_from_html(test_html, filename="smoke.pdf", inline=True)
    except Exception as e:
        logging.exception("Smoke failed")
        return jsonify({"error": "smoke_failed", "detail": str(e)}), 500


@app.get("/report/preview")
def report_preview():
    """Quick HTML preview of the PDF template with session data."""
    structured = session.get("structured", {}) or {}
    patient = session.get("patient", {}) or {}
    return render_template("pdf_report.html", structured=structured, patient=patient)


@app.route("/", methods=["GET"])
@app.route("/projects")
def projects():
    stats = db.get_stats()
    return render_template(
        "projects.html",
        posts=BLOG_POSTS,
        marquee_images=MARQUEE_IMAGES,
        submit_url="mailto:editor@insideimaging.example?subject=Radiologist%20Blog%20Pitch",
        stats=stats,
        languages=LANGUAGES,
    )


@app.route("/magazine")
def magazine():
    archive = []
    magazine_url = None

    for item in MAGAZINE_ISSUES:
        record = dict(item)
        raw_url = record.get("url")
        resolved_url = None
        if raw_url:
            if raw_url.startswith(("http://", "https://", "/")):
                resolved_url = raw_url
            else:
                resolved_url = url_for("static", filename=raw_url.lstrip("/"))
            record["url"] = resolved_url
            if magazine_url is None:
                magazine_url = resolved_url
        archive.append(record)

    return render_template("language.html", magazine_url=magazine_url, archive=archive)


@app.route("/language")
def legacy_language():
    return redirect(url_for("magazine"))


@app.route("/blogs")
def blogs():
    # Dedicated blogs listing page - attempt to extract full post content from magazine PDF
    posts = []
    # locate local magazine PDF if present
    mag_pdf = os.path.join(app.root_path, 'static', 'magazine', 'July-2025.pdf')
    for p in BLOG_POSTS:
        post = dict(p)
        # If URL contains a page anchor like '#page=9' try to extract that page from the PDF
        url = post.get('url', '') or ''
        import re
        m = re.search(r'page=(\d+)', url)
        if m and os.path.exists(mag_pdf):
            try:
                from pdfminer.high_level import extract_text
                page_num = int(m.group(1))
                # pdfminer uses 0-based page numbers
                text = extract_text(mag_pdf, page_numbers=[page_num - 1]) or ''
                # Basic cleanup
                text = text.strip()
                # Only overwrite `post['content']` from the PDF if the post has no
                # content defined in `BLOG_POSTS`. This ensures edits in `app.py`
                # are preserved and not clobbered by automatic PDF extraction.
                if text and not post.get('content'):
                    post['content'] = text
            except Exception:
                logging.exception('Failed to extract blog content from PDF')
        posts.append(post)

    return render_template("blogs.html", posts=posts, languages=LANGUAGES)


@app.route("/report_status")
def report_status():
    stats = db.get_stats()
    
    # Prepare JSON-safe data for JavaScript
    stats_json = {
        "reportsTimeSeries": stats.get("time_series", []),
        "ageData": [{"label": label, "value": count} for label, count in stats.get("age_ranges", {}).items()],
        "genderData": [
            {"label": "Female", "value": stats.get("gender", {}).get("female", 0)},
            {"label": "Male", "value": stats.get("gender", {}).get("male", 0)},
            {"label": "Other", "value": stats.get("gender", {}).get("other", 0)}
        ],
        "languagesData": stats.get("languages", []),
        "modalitiesData": stats.get("studies", []),
        "findingsData": [{"label": entry["label"].capitalize(), "value": entry["count"]} for entry in stats.get("diseases", [])]
    }
    
    return render_template("report_status.html", stats=stats, stats_json=stats_json)


@app.route("/payment")
def payment():
    # supply context expected by template
    structured_session = session.get("structured")
    if isinstance(structured_session, dict):
        structured = dict(structured_session)
    else:
        structured = {}

    structured.setdefault("report_type", "CT Scan")
    structured["price"] = f"{USD_PER_REPORT:.2f}"
    session["structured"] = structured

    kes_amount = USD_PER_REPORT * KES_PER_USD
    kes_display = f"{kes_amount:,.2f}".rstrip("0").rstrip(".")
    pricing = {
        "usd": USD_PER_REPORT,
        "usd_display": f"{USD_PER_REPORT:.2f}",
        "kes": kes_amount,
        "kes_display": kes_display,
        "tokens": TOKENS_PER_REPORT,
        "exchange_rate": KES_PER_USD,
    }
    lang = session.get("language", "English")
    return render_template("payment.html", structured=structured, language=lang, pricing=pricing)


@app.route("/help")
def help_page():
    return render_template("help.html")


@app.route("/team")
def team():
    """Team page with member bios and photos"""
    return render_template("team.html")


@app.route("/profile")
def profile():
    username = session.get("username")
    if not username:
        return redirect(url_for("login"))
    
    # Get user's feedback submissions
    user_feedback = db.get_user_feedback(username)
    
    # Check if user is admin (for now, hardcoded check - you can enhance this)
    is_admin = username in ["admin", "radiologist"]
    
    return render_template("profile.html", feedback_list=user_feedback, is_admin=is_admin)


@app.route("/submit-feedback", methods=["POST"])
def submit_feedback():
    """Handle feedback submission from radiologists/users"""
    username = session.get("username")
    if not username:
        flash("Please log in to submit feedback.", "error")
        return redirect(url_for("login"))
    
    try:
        feedback_type = request.form.get("feedback_type", "").strip()
        subject = request.form.get("subject", "").strip()
        original_text = request.form.get("original_text", "").strip()
        corrected_text = request.form.get("corrected_text", "").strip()
        description = request.form.get("description", "").strip()
        
        if not feedback_type or not subject:
            flash("Please provide feedback type and subject.", "error")
            return redirect(url_for("profile"))
        
        feedback_id = db.submit_feedback(
            username=username,
            feedback_type=feedback_type,
            subject=subject,
            original=original_text,
            corrected=corrected_text,
            description=description
        )
        
        logging.info("Feedback #%d submitted by %s: %s - %s", feedback_id, username, feedback_type, subject)
        flash("Thank you! Your feedback has been submitted successfully.", "success")
        
    except Exception as e:
        logging.exception("Failed to submit feedback")
        flash("Sorry, there was an error submitting your feedback. Please try again.", "error")
    
    return redirect(url_for("profile"))


@app.route("/feedback-admin")
def feedback_admin():
    """Admin view to review all feedback submissions"""
    username = session.get("username")
    if not username:
        return redirect(url_for("login"))
    
    # Check if user is admin
    is_admin = username in ["admin", "radiologist"]
    if not is_admin:
        flash("Access denied. Admin privileges required.", "error")
        return redirect(url_for("profile"))
    
    # Get filter status from query params
    status_filter = request.args.get("status", "pending")
    if status_filter == "all":
        all_feedback = db.get_all_feedback()
    else:
        all_feedback = db.get_all_feedback(status=status_filter)
    
    return render_template("feedback_admin.html", feedback_list=all_feedback, status_filter=status_filter)


@app.route("/review-feedback/<int:feedback_id>", methods=["POST"])
def review_feedback(feedback_id):
    """Admin action to approve/reject feedback"""
    username = session.get("username")
    if not username:
        return redirect(url_for("login"))
    
    # Check if user is admin
    is_admin = username in ["admin", "radiologist"]
    if not is_admin:
        flash("Access denied. Admin privileges required.", "error")
        return redirect(url_for("feedback_admin"))
    
    try:
        status = request.form.get("status", "").strip()
        admin_notes = request.form.get("admin_notes", "").strip()
        
        if status not in ["approved", "rejected", "implemented"]:
            flash("Invalid status.", "error")
            return redirect(url_for("feedback_admin"))
        
        db.update_feedback_status(
            feedback_id=feedback_id,
            status=status,
            reviewed_by=username,
            admin_notes=admin_notes
        )
        
        logging.info("Feedback #%d reviewed by %s: %s", feedback_id, username, status)
        flash(f"Feedback #{feedback_id} marked as {status}.", "success")
        
    except Exception as e:
        logging.exception("Failed to review feedback")
        flash("Sorry, there was an error processing your request.", "error")
    
    return redirect(url_for("feedback_admin"))


@app.route("/contact-support", methods=["POST"])
def contact_support():
    """Handle contact support form submission"""
    try:
        name = request.form.get("name", "").strip()
        email = request.form.get("email", "").strip()
        subject = request.form.get("subject", "").strip()
        message = request.form.get("message", "").strip()
        
        # Log the support request (in production, send email or save to database)
        logging.info("Support request from %s (%s): %s - %s", name, email, subject, message)
        
        flash("Thank you for contacting us! We'll get back to you soon.", "success")
    except Exception as e:
        logging.exception("Failed to process support request")
        flash("Sorry, there was an error submitting your message. Please try again.", "error")
    
    return redirect(url_for("help_page"))


@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        username = request.form.get("username", "").strip()
        password = request.form.get("password", "")
        user = db.get_user_by_username(username)
        if user and check_password_hash(user["password_hash"], password):
            session["username"] = username
            flash("Logged in successfully.", "success")
            return redirect(url_for("dashboard"))
        flash("Invalid username or password.", "error")
    return render_template("login.html")


@app.route("/signup", methods=["GET", "POST"])
def signup():
    if request.method == "POST":
        username = request.form.get("username", "").strip()
        password = request.form.get("password", "")
        if db.get_user_by_username(username):
            flash("Username already exists. Please choose a different one.", "error")
        else:
            password_hash = generate_password_hash(password)
            db.create_user(username, password_hash)
            flash("Account created successfully. Please log in.", "success")
            return redirect(url_for("login"))
    return render_template("signup.html")


@app.route("/logout")
def logout():
    session.clear()  # Clear entire session instead of just username
    flash("Logged out successfully.", "success")
    return redirect(url_for("login"))


if __name__ == "__main__":
    # Use app.run only for local dev. For prod use a WSGI server.
    app.run(debug=True)
