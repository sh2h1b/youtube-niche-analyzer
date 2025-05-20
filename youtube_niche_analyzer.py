import os
import pandas as pd
from googleapiclient.discovery import build
from requests_html import HTMLSession
import matplotlib.pyplot as plt
from datetime import datetime
import streamlit as st

# Configuration
API_KEY = "AIzaSyA7esa9GEjPZCecMk1-uKsvNq61c2AsX7E"  # Replace with your actual API key
MAX_CHANNELS = 50  # Maximum channels to analyze
RESULTS_DIR = "results"
os.makedirs(RESULTS_DIR, exist_ok=True)

# Initialize YouTube API
youtube = build('youtube', 'v3', developerKey=API_KEY)

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
    st.write("### Step 1: Finding seed channels...")
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
    
    # Step 2: Find related channels for each seed channel
    st.write("### Step 2: Discovering related channels...")
    all_channels = set(seed_channels)
    progress_bar = st.progress(0)
    
    for i, channel_id in enumerate(seed_channels):
        channel_url = f"https://www.youtube.com/channel/{channel_id}"
        related = get_related_channels(channel_url, max_channels=5)
        all_channels.update(related)
        progress_bar.progress((i + 1) / len(seed_channels))
    
    # Step 3: Get stats for all channels
    st.write("### Step 3: Gathering channel statistics...")
    channel_data = []
    progress_bar = st.progress(0)
    
    for i, channel_id in enumerate(list(all_channels)[:MAX_CHANNELS]):
        stats = get_channel_stats(channel_id)
        if stats:
            # Get top videos
            videos = get_channel_videos(channel_id)
            stats['top_videos'] = videos
            channel_data.append(stats)
        progress_bar.progress((i + 1) / min(len(all_channels), MAX_CHANNELS))
    
    # Classify channels by size
    for channel in channel_data:
        subs = channel['subscribers']
        if subs < 10000:
            channel['size'] = "Small (0-10K)"
        elif subs < 100000 :
            channel['size'] = "Medium (10K-100K)"
        elif subs < 1000000:
            channel['size'] = "Large (100K-1M)"
        else:
            channel['size'] = "Very Large (1M+)"
    
    return channel_data

def visualize_data(channel_data):
    """Create visualizations of the channel data"""
    st.write("## 📊 Niche Analysis Results")
    
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
    fig, ax = plt.subplots()
    size_counts.plot(kind='bar', ax=ax, color='skyblue')
    plt.xticks(rotation=45)
    st.pyplot(fig)
    
    # Subscribers vs. Channel Age
    st.write("### Subscribers vs. Channel Age")
    fig, ax = plt.subplots(figsize=(10, 6))
    for size, group in df.groupby('size'):
        ax.scatter(group['age_months'], group['subscribers'] / 1000, label=size, alpha=0.6)
    ax.set_xlabel('Channel Age (months)')
    ax.set_ylabel('Subscribers (in thousands)')
    ax.set_yscale('log')
    ax.legend()
    st.pyplot(fig)
    
    # Top video analysis
    st.write("### Top Video Analysis")
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
    st.set_page_config(page_title="YouTube Niche Analyzer", layout="wide")
    
    st.title("🎬 YouTube Niche Analyzer")
    st.markdown("""
    Analyze any YouTube niche by finding similar channels at all levels (small, medium, large).
    This tool helps content creators research competition and identify opportunities.
    """)
    
    with st.sidebar:
        st.header("Settings")
        keyword = st.text_input("Enter a niche keyword:", "vegan cooking")
        analyze_btn = st.button("Analyze Niche")
    
    if analyze_btn:
        with st.spinner("Analyzing niche. This may take a few minutes..."):
            channel_data = analyze_niche(keyword)
            
            if channel_data:
                df = visualize_data(channel_data)
                filename = save_results(channel_data, keyword)
                
                st.success(f"Analysis complete! Found {len(channel_data)} channels.")
                st.download_button(
                    label="Download Full Data",
                    data=open(filename, 'rb').read(),
                    file_name=os.path.basename(filename),
                    mime="text/csv"
                )
                
                st.write("## 🏆 Top Channels in This Niche")
                cols = st.columns(3)
                
                for i, channel in enumerate(sorted(channel_data, key=lambda x: x['subscribers'], reverse=True)[:12]):
                    with cols[i % 3]:
                        st.image(channel['thumbnail'], width=150)
                        st.subheader(channel['name'])
                        st.caption(f"📊 {channel['size']}")
                        st.caption(f"👥 {channel['subscribers']:,} subs")
                        st.caption(f"🎥 {channel['videos']} videos")
                        
            else:
                st.error("just wanna test it, hands up")

if __name__ == "__main__":
    main()