import os
import pandas as pd
from googleapiclient.discovery import build
from requests_html import HTMLSession
import matplotlib.pyplot as plt
from datetime import datetime
import streamlit as st
import uuid

st.set_page_config(page_title="YouTube Niche Analyzer", layout="wide")


# Configuration
API_KEY = "AIzaSyA7esa9GEjPZCecMk1-uKsvNq61c2AsX7E"  # Replace with your actual API key
MAX_CHANNELS = 50  # Maximum channels to analyze
RESULTS_DIR = "results"
os.makedirs(RESULTS_DIR, exist_ok=True)

# Initialize YouTube API
youtube = build('youtube', 'v3', developerKey=API_KEY)

# Custom CSS for minimal blue and yellow design
st.markdown("""
<style>
    /* General styling */
    .stApp {
        background-color: #F8FAFC;
        font-family: 'Inter', sans-serif;
    }
    
    /* Main title */
    h1 {
        color: #1E3A8A;
        font-size: 2.5rem;
        font-weight: 700;
        margin-bottom: 1rem;
    }
    
    /* Sidebar styling */
    .css-1d391kg {
        background-color: #1E3A8A;
        color: #FFFFFF;
        padding: 1.5rem;
    }
    .css-1d391kg h2 {
        color: #FBBF24;
        font-size: 1.5rem;
        font-weight: 600;
    }
    .css-1d391kg .stTextInput > div > div > input {
        background-color: #FFFFFF;
        border: 1px solid #3B82F6;
        border-radius: 8px;
        padding: 0.5rem;
        color: #1E3A8A;
    }
    .css-1d391kg .stButton > button {
        background-color: #FBBF24;
        color: #1E3A8A;
        border: none;
        border-radius: 8px;
        padding: 0.75rem 1.5rem;
        font-weight: 600;
        width: 100%;
        transition: background-color 0.2s;
    }
    .css-1d391kg .stButton > button:hover {
        background-color: #F59E0B;
    }
    
    /* Content styling */
    .stSpinner .spinner {
        border-top-color: #3B82F6;
    }
    .stInfo, .stSuccess, .stError {
        border-radius: 8px;
        background-color: #E6F0FA;
        color: #1E3A8A;
        border: 1px solid #3B82F6;
    }
    .stDownloadButton > button {
        background-color: #3B82F6;
        color: #FFFFFF;
        border-radius: 8px;
        padding: 0.5rem 1rem;
        font-weight: 600;
    }
    .stDownloadButton > button:hover {
        background-color: #2563EB;
    }
    
    /* Card styling for channels */
    .channel-card {
        background-color: #FFFFFF;
        border: 1px solid #E2E8F0;
        border-radius: 8px;
        padding: 1rem;
        margin-bottom: 1rem;
        transition: box-shadow 0.2s;
    }
    .channel-card:hover {
        box-shadow: 0 4px 6px rgba(0, 0, 0, 0.1);
    }
    .channel-card img {
        border-radius: 50%;
        margin-bottom: 0.5rem;
    }
    .channel-card h3 {
        color: #1E3A8A;
        font-size: 1.25rem;
        margin: 0.5rem 0;
    }
    .channel-card p {
        color: #64748B;
        font-size: 0.9rem;
        margin: 0.25rem 0;
    }
    
    /* Plot styling */
    .plt-figure {
        background-color: #FFFFFF;
        padding: 1rem;
        border-radius: 8px;
        border: 1px solid #E2E8F0;
    }
</style>
""", unsafe_allow_html=True)

def get_channel_stats(channel_id):
    """Fetch channel statistics"""
    request = youtube.channels().list(
        part="statistics,snippet",
        id=channel_id
    )
    response = request.execute()
    if not response['items']:
        return None
    
    stats = response['items'][0]['statistics']
    snippet = response['items'][0]['snippet']
    
    return {
        'id': channel_id,
        'name': snippet['title'],
        'subscribers': int(stats.get('subscriberCount', 0)),
        'views': int(stats.get('viewCount', 0)),
        'videos': int(stats.get('videoCount', 0)),
        'thumbnail': snippet['thumbnails']['default']['url'],
        'description': snippet['description'],
        'created_at': snippet['publishedAt']
    }

def get_channel_videos(channel_id, max_results=5):
    """Fetch top videos from a channel"""
    request = youtube.search().list(
        part="snippet",
        channelId=channel_id,
        maxResults=max_results,
        order="viewCount",
        type="video"
    )
    response = request.execute()
    
    videos = []
    for item in response['items']:
        videos.append({
            'title': item['snippet']['title'],
            'id': item['id']['videoId'],
            'thumbnail': item['snippet']['thumbnails']['default']['url'],
            'published_at': item['snippet']['publishedAt']
        })
    return videos

def get_related_channels(channel_url, max_channels=10):
    """Scrape YouTube for related channels"""
    session = HTMLSession()
    try:
        r = session.get(channel_url + "/channels")
        r.html.render(sleep=2, timeout=20)
        channels = []
        
        for element in r.html.find('a#channel-info'):
            channel_id = element.attrs.get('href', '').split('/')[-1]
            if channel_id.startswith('@') or channel_id.startswith('channel'):
                channels.append(channel_id)
                if len(channels) >= max_channels:
                    break
        return list(set(channels))  # Remove duplicates
    except Exception as e:
        print(f"Error scraping: {e}")
        return []

def analyze_niche(keyword):
    """Main analysis function"""
    st.info(f"🔍 Analyzing niche: {keyword}")
    
    # Step 1: Search for channels by keyword
    st.write("### Finding Channels")
    search_request = youtube.search().list(
        q=keyword,
        part="snippet",
        type="channel",
        maxResults=10
    )
    search_response = search_request.execute()
    
    seed_channels = []
    for item in search_response['items']:
        channel_id = item['snippet']['channelId']
        seed_channels.append(channel_id)
    
    # Step 2: Find related channels
    st.write("### Discovering Related Channels")
    all_channels = set(seed_channels)
    progress_bar = st.progress(0)
    
    for i, channel_id in enumerate(seed_channels):
        channel_url = f"https://www.youtube.com/channel/{channel_id}"
        related = get_related_channels(channel_url, max_channels=5)
        all_channels.update(related)
        progress_bar.progress((i + 1) / len(seed_channels))
    
    # Step 3: Get stats for all channels
    st.write("### Gathering Statistics")
    channel_data = []
    progress_bar = st.progress(0)
    
    for i, channel_id in enumerate(list(all_channels)[:MAX_CHANNELS]):
        stats = get_channel_stats(channel_id)
        if stats:
            videos = get_channel_videos(channel_id)
            stats['top_videos'] = videos
            channel_data.append(stats)
        progress_bar.progress((i + 1) / min(len(all_channels), MAX_CHANNELS))
    
    # Classify channels by size
    for channel in channel_data:
        subs = channel['subscribers']
        if subs < 10000:
            channel['size'] = "Small (0-10K)"
        elif subs < 100000:
            channel['size'] = "Medium (10K-100K)"
        elif subs < 1000000:
            channel['size'] = "Large (100K-1M)"
        else:
            channel['size'] = "Very Large (1M+)"
    
    return channel_data

def visualize_data(channel_data):
    """Create visualizations of the channel data"""
    st.write("## 📊 Analysis Results")
    
    # Create DataFrame with proper datetime handling
    df = pd.DataFrame(channel_data)
    
    # Convert datetime strings to datetime objects
    df['created_at'] = pd.to_datetime(df['created_at'], format='ISO8601')
    
    # Calculate channel age
    from datetime import timezone
    df['age_months'] = ((datetime.now(timezone.utc) - df['created_at']).dt.days / 30).round()
    df['subs_per_video'] = df['subscribers'] / df['videos']
    
    # Channel size distribution
    st.write("### Channel Size Distribution")
    size_counts = df['size'].value_counts()
    fig, ax = plt.subplots(figsize=(8, 5))
    size_counts.plot(kind='bar', ax=ax, color='#3B82F6')
    plt.xticks(rotation=45)
    plt.xlabel('Channel Size', fontsize=12, color='#1E3A8A')
    plt.ylabel('Count', fontsize=12, color='#1E3A8A')
    plt.title('Distribution of Channels by Size', fontsize=14, color='#1E3A8A')
    st.pyplot(fig)
    
    # Subscribers vs. Channel Age
    st.write("### Subscribers vs. Channel Age")
    fig, ax = plt.subplots(figsize=(10, 6))
    for size, group in df.groupby('size'):
        ax.scatter(group['age_months'], group['subscribers'] / 1000, label=size, alpha=0.6, color='#3B82F6')
    ax.set_xlabel('Channel Age (months)', fontsize=12, color='#1E3A8A')
    ax.set_ylabel('Subscribers (in thousands)', fontsize=12, color='#1E3A8A')
    ax.set_yscale('log')
    ax.legend()
    ax.grid(True, linestyle='--', alpha=0.7)
    plt.title('Subscribers vs. Channel Age', fontsize=14, color='#1E3A8A')
    st.pyplot(fig)
    
    # Top video analysis (simplified for minimalism)
    st.write("### Top Videos")
    all_videos = []
    for channel in channel_data:
        for video in channel['top_videos']:
            video['channel_name'] = channel['name']
            video['channel_size'] = channel['size']
            video['published_at'] = pd.to_datetime(video['published_at'], format='ISO8601')
            all_videos.append(video)
    
    video_df = pd.DataFrame(all_videos)
    video_df['title_length'] = video_df['title'].apply(len)
    
    return df

def save_results(channel_data, keyword):
    """Save analysis results to CSV"""
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    filename = f"{RESULTS_DIR}/{keyword.replace(' ', '_')}_{timestamp}.csv"

    # Flatten data for CSV
    records = []
    for channel in channel_data:
        record = {
            'channel_id': channel['id'],
            'channel_name': channel['name'],
            'subscribers': channel['subscribers'],
            'views': channel['views'],
            'videos': channel['videos'],
            'channel_size': channel['size'],
            'created_at': channel['created_at'],
            'description': channel['description']
        }

        # Add top videos
        for i, video in enumerate(channel['top_videos'], 1):
            record[f'top_video_{i}_title'] = video['title']
            record[f'top_video_{i}_id'] = video['id']
            record[f'top_video_{i}_published'] = video['published_at']

        records.append(record)

    pd.DataFrame(records).to_csv(filename, index=False)
    return filename


# Streamlit UI
def main():
    
    st.title("🎬 YouTube Niche Analyzer")
    st.markdown("Analyze YouTube niches to discover channels and identify opportunities.", unsafe_allow_html=True)
    
    with st.sidebar:
        st.header("Analyze a Niche")
        keyword = st.text_input("Enter niche keyword:", "vegan cooking", help="Enter a keyword to analyze related YouTube channels.")
        analyze_btn = st.button("Analyze", use_container_width=True)
    
    if analyze_btn:
        with st.spinner("Analyzing niche..."):
            channel_data = analyze_niche(keyword)
            
            if channel_data:
                df = visualize_data(channel_data)
                filename = save_results(channel_data, keyword)
                
                st.success(f"Found {len(channel_data)} channels in the {keyword} niche!")
                st.download_button(
                    label="Download Data",
                    data=open(filename, 'rb').read(),
                    file_name=os.path.basename(filename),
                    mime="text/csv",
                    use_container_width=True
                )
                
                st.write("## 🏆 Top Channels")
                st.markdown("Explore the top channels in this niche, sorted by subscriber count.")
                for channel in sorted(channel_data, key=lambda x: x['subscribers'], reverse=True)[:12]:
                    with st.container():
                        st.markdown(
                            f"""
                            <div class="channel-card">
                                <img src="{channel['thumbnail']}" width="80">
                                <h3>{channel['name']}</h3>
                                <p>{channel['size']}</p>
                                <p>{channel['subscribers']:,} subscribers</p>
                                <p>{channel['videos']} videos</p>
                            </div>
                            """,
                            unsafe_allow_html=True
                        )
            else:
                st.error("No channels found. Try a different keyword.")

if __name__ == "__main__":
    main()
