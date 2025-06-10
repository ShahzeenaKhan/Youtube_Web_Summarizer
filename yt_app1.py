import re
import validators
import streamlit as st
from validators import url as is_url
import requests
from bs4 import BeautifulSoup
from youtube_transcript_api import YouTubeTranscriptApi
from langchain.docstore.document import Document
from langchain.prompts import PromptTemplate
from langchain_groq import ChatGroq
from langchain.chains.summarize import load_summarize_chain
from functools import lru_cache

# Page config
st.set_page_config(page_title="URL → Summary", page_icon="📺")
st.title("🌏 → 📑 Text Summarizer")
st.subheader("Summarize a YouTube video or any webpage")

# Sidebar
with st.sidebar:
    st.markdown(
        """
        📜 **How to use**:
        1. Enter your GROQ API Key.
        2. Adjust summary length if you like.
        3. Paste a YouTube or webpage URL.
        4. Press Summarize.
        """
    )
    groq_api_key = st.text_input("GROQ_API_KEY", type="password")
    summary_length = st.slider("Summary Length (words)", 100, 500, 300, step=50)

# Main input
generic_url = st.text_input("URL :", label_visibility="collapsed", 
                           placeholder="Paste YouTube or webpage URL here")

@lru_cache(maxsize=32)
def get_cached_transcript(video_id):
    try:
        transcript_list = YouTubeTranscriptApi.list_transcripts(video_id)
        transcript = transcript_list.find_transcript(['en'])
        return transcript.fetch()
    except Exception as e:
        raise e

def get_video_id(url):
    """Improved YouTube video ID extraction"""
    patterns = [
        r"(?:v=|\/)([0-9A-Za-z_-]{11})",
        r"youtu\.be\/([0-9A-Za-z_-]{11})",
        r"embed\/([0-9A-Za-z_-]{11})",
        r"\/shorts\/([0-9A-Za-z_-]{11})"
    ]
    for pat in patterns:
        try:
            match = re.search(pat, url)
            if match:
                return match.group(1)
        except:
            continue
    return None

def extract_youtube_metadata(url):
    """Fallback for when transcripts aren't available"""
    try:
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)",
            "Accept-Language": "en-US,en;q=0.9"
        }
        response = requests.get(url, headers=headers, timeout=10)
        soup = BeautifulSoup(response.text, 'html.parser')
        
        title = soup.find("meta", {"property": "og:title"})["content"]
        description = soup.find("meta", {"property": "og:description"})["content"]
        return f"Video Title: {title}\n\nDescription: {description}"
    except:
        return None

if not groq_api_key.strip():
    st.warning("🔑 Please enter your GROQ API Key", icon="🚨")
else:
    if st.button("📝 Summarize"):
        if not generic_url.strip():
            st.error("Please enter a URL to get started")
        elif not is_url(generic_url):
            st.error("Please enter a valid URL (e.g. a YouTube link or webpage)")
        else:
            docs = []
            try:
                with st.spinner("Fetching content…"):
                    # YouTube transcript path
                    if "youtube.com" in generic_url or "youtu.be" in generic_url:
                        video_id = get_video_id(generic_url)
                        if not video_id:
                            st.error("❌ Could not extract YouTube video ID from URL")
                        else:
                            try:
                                transcript = get_cached_transcript(video_id)
                                transcript_text = " ".join([seg["text"] for seg in transcript])
                                docs = [Document(page_content=transcript_text)]
                            except Exception as e:
                                st.warning(f"⚠️ Could not fetch transcript: {str(e)}")
                                # Try fallback metadata extraction
                                fallback_text = extract_youtube_metadata(generic_url)
                                if fallback_text:
                                    st.info("Using video title/description as fallback content")
                                    docs = [Document(page_content=fallback_text)]
                                else:
                                    st.error("No transcript available and couldn't extract fallback content")

                    # Webpage path
                    else:
                        headers = {
                            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)",
                            "Accept-Language": "en-US,en;q=0.9"
                        }
                        response = requests.get(generic_url, headers=headers, timeout=15)
                        if response.status_code == 200:
                            soup = BeautifulSoup(response.text, "html.parser")
                            # Remove script and style elements
                            for script in soup(["script", "style"]):
                                script.decompose()
                            paragraphs = soup.find_all("p")
                            page_text = " ".join([p.get_text().strip() for p in paragraphs if p.get_text().strip()])
                            if len(page_text) < 100:
                                st.warning("⚠️ Very little visible text found; summary may be short.")
                            docs = [Document(page_content=page_text)]
                        else:
                            st.error(f"Failed to fetch page (status code {response.status_code})")

                if docs:
                    with st.spinner("Summarizing…"):
                        llm = ChatGroq(model="llama3-8b-8192", api_key=groq_api_key)
                        prompt = PromptTemplate(
                            template=(
                                f"Provide a concise summary of the following content in about {summary_length} words:\n\n{{text}}"
                            ),
                            input_variables=["text"],
                        )
                        chain = load_summarize_chain(llm, chain_type="stuff", prompt=prompt)
                        summary = chain.run(docs)

                    st.success("✅ Done!")
                    st.markdown("### Summary")
                    st.write(summary)
                else:
                    st.error("No content to summarize. Please check the URL or try another link.")

            except Exception as err:
                st.error(f"An unexpected error occurred: {err}")

st.markdown("---")
st.markdown(
    "Built with 👨🏻‍🎓 Data Science Batch 01 👩🏻‍🎓 using [Streamlit] / [Langchain] / [GroqAPI]"
)