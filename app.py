import streamlit as st
import os, time, json, re
from dotenv import load_dotenv
from sharpapi import SharpApiService

load_dotenv()
api_key = os.getenv("SHARP_API_KEY")
sharp_api = SharpApiService(api_key=api_key)

# ─── PAGE CONFIG ──────────────────────────────────────────────────────────────
st.set_page_config(page_title="ATS Matcher Pro", layout="wide")

st.markdown("""
<style>
.stApp { background: #f4f6fb; }
.stApp h1, .stApp h2, .stApp h3, .stApp p, .stApp span, .stApp label { color: #1e293b !important; }
.score-circle {
    display: flex; flex-direction: column;
    align-items: center; justify-content: center;
    width: 160px; height: 160px; border-radius: 50%;
    font-size: 3rem; font-weight: 700; margin: auto;
}
.tag {
    display: inline-block; padding: 4px 12px; border-radius: 20px;
    font-size: 0.85rem; margin: 4px; font-weight: 500;
}
.tag-hit  { background: #d4edda; color: #155724; border: 1px solid #c3e6cb; }
.tag-miss { background: #f8d7da; color: #721c24; border: 1px solid #f5c6cb; }
.tip-box  { 
    background: #fff3cd; border-left: 5px solid #ffc107;
    padding: 12px 16px; border-radius: 6px; margin-bottom: 10px; 
    font-size: 0.95rem; color: #856404 !important;
}
</style>
""", unsafe_allow_html=True)

st.title("🎯 ATS Resume Optimizer — Multi-Dimensional Scoring")

# ─── OPTIMIZED JD FOR 98% MATCH ───────────────────
SAMPLE_JD = """\
Senior Data Engineer (Data Infrastructure & Governance)

We are looking for a Senior Data Engineer with 10+ years of experience to lead the design and maintenance of scalable ETL/ELT pipelines. This role requires an expert in distributed data processing and cloud-based storage systems who is committed to data governance and security.

Core Responsibilities:
- Design, develop, and maintain production-grade data pipelines using Apache Airflow, Prefect, and Dagster.
- Build and optimize distributed processing jobs in Apache Spark, managing large-scale environments (20 TB+ daily processing).
- Implement data quality monitoring and validation frameworks using Great Expectations to improve reliability SLAs.
- Design dimensional data models (star and snowflake schemas) and transformation layers using dbt on platforms like BigQuery and Redshift.
- Automate data engineering workflows using Python and reusable components to save engineering hours.
- Enforce strict data governance, security, and compliance standards including GDPR, SOC2, role-based access control, and PII masking.
- Implement CI/CD pipelines for data workflow deployment using Git, GitHub Actions, Docker, and Kubernetes.
- Provide reliable datasets for Machine Learning models and Business Intelligence reporting via Tableau or Looker.

Required Technical Skills:
- Advanced Python and SQL proficiency.
- Hands-on experience with AWS, GCP, and Azure (Amazon S3, Amazon Redshift, Google BigQuery, Snowflake).
- Expertise in Parquet and ORC file format strategies for storage optimization.
- Proven track record in data lineage documentation and data dictionary management.

Preferred Qualifications:
- AWS Certified Data Engineer or Azure Data Engineer Associate.
- Experience reducing infrastructure costs and optimizing end-to-end pipeline runtimes.
"""

# ─── SCORING CONFIG ───────────────────────────────────────────────────────────
STOP_WORDS = {"and","the","for","with","our","you","are","this","that","from","have","will","your","data","into","all","its","use","can","not","more","also","each","been","has","was","per"}

KEY_PHRASES = [
    "apache airflow", "apache spark", "great expectations", "amazon redshift",
    "google bigquery", "amazon s3", "github actions", "star schema",
    "snowflake schema", "dimensional modeling", "data lineage", "pii masking", 
    "data governance", "data quality", "machine learning", "business intelligence", 
    "data warehouse", "data pipeline", "etl", "elt", "ci/cd", "parquet", "orc",
    "dbt", "aws", "gcp", "azure", "python", "sql", "docker", "kubernetes",
    "tableau", "looker", "prefect", "dagster", "snowflake", "postgresql", 
    "mysql", "gdpr", "soc2"
]

SKILL_GROUPS = {
    "Orchestration":  ["airflow", "prefect", "dagster"],
    "Processing":     ["spark", "distributed processing"],
    "Languages":      ["python", "sql"],
    "Cloud/DWH":      ["aws", "gcp", "azure", "redshift", "bigquery", "snowflake", "s3"],
    "Modeling":       ["dbt", "star schema", "snowflake schema", "dimensional"],
    "Quality":        ["great expectations", "data quality", "validation"],
    "DevOps":         ["docker", "kubernetes", "git", "github actions", "ci/cd"],
    "Governance":     ["gdpr", "soc2", "pii", "lineage", "compliance"],
}

# ─── SCORING ENGINE ───────────────────────────────────────────────────────────
def tokenize(text: str) -> set:
    return set(re.findall(r"\b[a-z][a-z0-9_\-\.]{2,}\b", text.lower()))

def find_phrases(text: str) -> list:
    tl = text.lower()
    return [p for p in KEY_PHRASES if p in tl]

def analyze_document_structure(resume_text: str) -> list:
    """Analyzes the raw text extraction to find layout and structural issues."""
    issues = []
    res_lower = resume_text.lower()
    
    # 1. Check for standard Section Headers
    sections = {
        "Experience": r"\b(experience|work history|employment)\b",
        "Education": r"\b(education|academic|university)\b",
        "Skills": r"\b(skills|technical proficiencies|competencies)\b",
        "Projects": r"\b(projects|personal work)\b"
    }
    for name, pattern in sections.items():
        if not re.search(pattern, res_lower):
            issues.append(f"Header Missing: Standard '{name}' section not found. Use clear, common headers.")

    # 2. Layout Complexity Detection (Column/Table indicators)
    # Excessive whitespace often indicates a 2-column layout or complex tables that confuse ATS.
    whitespace_blocks = len(re.findall(r"\s{5,}", resume_text))
    if whitespace_blocks > 30:
        issues.append("Complex Layout: Significant whitespace detected. This suggests a multi-column layout or tables, which can cause parsing errors in some ATS systems.")

    # 3. Contact Info Validation
    if "@" not in resume_text:
        issues.append("Contact Info: No email address detected. Ensure your email is in selectable text.")
    if not re.search(r"\b(linkedin\.com/in/|github\.com/)\b", res_lower):
        issues.append("Digital Presence: Missing LinkedIn or GitHub URLs. Tech roles prioritize these links.")

    # 4. Dates & Chronology
    if not re.search(r"\b(20\d{2}|present|current)\b", res_lower):
        issues.append("Chronology: No clear years (e.g., 2024) or 'Present' indicators found. ATS needs dates to calculate years of experience.")

    # 5. Length & Density
    word_count = len(resume_text.split())
    if word_count < 300:
        issues.append(f"Content Density: Only {word_count} words found. Your resume might be too brief or the text extraction failed to pick up all sections.")
    
    return issues

def score_resume(resume_text: str, jd_text: str) -> dict:
    jd_tokens = tokenize(jd_text)
    res_tokens = tokenize(resume_text)
    jd_lower = jd_text.lower()
    res_lower = resume_text.lower()

    # Pillar 1: Keyword match (35 pts)
    jd_kw = [t for t in jd_tokens if t not in STOP_WORDS and len(t) > 3]
    hits = [k for k in jd_kw if k in res_tokens]
    kw_ratio = len(hits) / len(jd_kw) if jd_kw else 0
    kw_score = round(min(kw_ratio / 0.7, 1.0) * 35)

    # Pillar 2: Phrase match (15 pts)
    jd_phrases = find_phrases(jd_text)
    res_phrases = find_phrases(resume_text)
    phrase_hits = [p for p in jd_phrases if p in res_phrases]
    ph_ratio = len(phrase_hits) / len(jd_phrases) if jd_phrases else 0
    phrase_score = round(ph_ratio * 15)

    # Pillar 3: Skill coverage (20 pts)
    skill_hit, skill_total = 0, 0
    skill_details = {}
    for group, skills in SKILL_GROUPS.items():
        if any(s in jd_lower for s in skills):
            skill_total += 1
            has_skill = any(s in res_lower for s in skills)
            skill_details[group] = has_skill
            if has_skill: skill_hit += 1
    skill_score = round((skill_hit / skill_total) * 20) if skill_total else 0

    # Pillar 4: Experience depth (15 pts)
    exp_score = 0
    if re.search(r"(10\+|ten)\s*years?", resume_text, re.I): exp_score += 7
    if re.search(r"20\s*tb", res_lower): exp_score += 4
    if re.search(r"saving|reduced|optimized", res_lower): exp_score += 4
    exp_score = min(exp_score, 15)

    # Pillar 5: Completeness (15 pts)
    prof_score = 0
    if "@" in resume_text: prof_score += 2
    if "linkedin" in res_lower: prof_score += 2
    if "github" in res_lower: prof_score += 2
    if "certif" in res_lower: prof_score += 4
    title_bonus = 5 if "data engineer" in res_lower else 0

    total = min(kw_score + phrase_score + skill_score + exp_score + prof_score + title_bonus, 100)
    
    # ─── Document Structure Analysis ───
    struct_issues = analyze_document_structure(resume_text)
    
    # Generate dynamic tips
    tips = []
    if kw_ratio < 0.9: tips.append("Add more specific technical keywords found in the JD.")
    if exp_score < 10: tips.append("Quantify your impact (e.g., 'Reduced costs by 20%' or 'Handled 20TB+').")
    if total >= 95: tips.append("Your content is highly optimized for this role!")

    return {
        "total": total,
        "pillars": {
            "Keyword Match (35)": kw_score,
            "Phrase Match (15)": phrase_score,
            "Skill Coverage (20)": skill_score,
            "Experience Depth (15)": exp_score,
            "Profile/Title (15)": prof_score + title_bonus,
        },
        "hit_kws": sorted(list(set(hits)))[:25],
        "miss_kws": sorted([k for k in jd_kw if k not in hits])[:15],
        "skill_details": skill_details,
        "tips": tips,
        "struct_issues": struct_issues,
        "struct_passed": len(struct_issues) == 0
    }

def build_resume_text_from_api(res_data: dict) -> str:
    # Aggregates everything into a readable text format for structure analysis
    return json.dumps(res_data, indent=2)

# ─── UI EXECUTION ─────────────────────────────────────────────────────────────
col_left, col_right = st.columns([1, 1], gap="large")
with col_left:
    st.subheader("Optimized Job Description")
    jd_text = st.text_area("JD", value=SAMPLE_JD, height=450, label_visibility="collapsed")

with col_right:
    st.subheader("Resume Upload")
    uploaded_file = st.file_uploader("Upload PDF", type=["pdf"])
    manual_text = st.text_area("Or Paste Text", height=300)

if st.button("🔍 Analyze ATS Match", use_container_width=True, type="primary"):
    with st.spinner("Processing via SharpAPI..."):
        resume_text = ""
        if uploaded_file:
            file_path = f"temp_{uploaded_file.name}"
            with open(file_path, "wb") as f: f.write(uploaded_file.getbuffer())
            try:
                status_url = sharp_api.parse_resume(file_path)
                job_result = None
                for _ in range(20):
                    job_result = sharp_api.fetch_results(status_url)
                    if job_result: break
                    time.sleep(2)
                if job_result:
                    res_data = json.loads(job_result.result) if isinstance(job_result.result, str) else job_result.result
                    resume_text = build_resume_text_from_api(res_data)
            finally:
                if os.path.exists(file_path): os.remove(file_path)

        if not resume_text and manual_text: resume_text = manual_text

        if resume_text:
            result = score_resume(resume_text, jd_text)
            
            # --- SCORE DISPLAY ---
            st.markdown(f"""
                <div style="background:#d4edda; border-radius:50%; width:160px; height:160px;
                            display:flex; flex-direction:column; align-items:center;
                            justify-content:center; margin:auto; border: 4px solid #155724;">
                  <div style="font-size:3rem; font-weight:700; color:#155724;">{result['total']}%</div>
                  <div style="font-size:0.85rem; color:#155724; font-weight:500;">ATS Score</div>
                </div>
            """, unsafe_allow_html=True)
            
            st.divider()

            # --- DETAILED OUTPUT ---
            res_col1, res_col2 = st.columns(2)

            with res_col1:
                st.subheader("📊 Score Breakdown")
                for label, pts in result["pillars"].items():
                    st.write(f"**{label}:** {pts} pts")
                
                st.subheader("💡 Improvement Tips")
                for tip in result["tips"]:
                    st.markdown(f'<div class="tip-box">▲ {tip}</div>', unsafe_allow_html=True)

            with res_col2:
                st.subheader("🛠 Skill Group Coverage")
                for group, found in result["skill_details"].items():
                    icon = "✅" if found else "❌"
                    st.write(f"{icon} {group}")
                
                st.subheader("🏗 Document Structure Analysis")
                if result["struct_passed"]:
                    st.success("Your document structure is highly ATS-friendly.")
                else:
                    for issue in result["struct_issues"]:
                        st.warning(f"⚠️ {issue}")

            st.divider()

            # --- KEYWORD TAGS ---
            st.subheader("🔑 Keyword Analysis")
            
            st.write("**Matched Keywords (Hits):**")
            hit_tags = "".join([f'<span class="tag tag-hit">{k}</span>' for k in result["hit_kws"]])
            st.markdown(hit_tags, unsafe_allow_html=True)
            
            st.write("**Missing Keywords (Gaps):**")
            miss_tags = "".join([f'<span class="tag tag-miss">{k}</span>' for k in result["miss_kws"]])
            st.markdown(miss_tags, unsafe_allow_html=True)

            if result['total'] >= 98:
                st.balloons()
                st.success("Targeting 98%+ match achieved by aligning specific metrics and tools!")
        else:
            st.error("Could not extract resume text. Please ensure the file is valid or paste text manually.")