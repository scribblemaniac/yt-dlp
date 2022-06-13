import re

from .common import InfoExtractor
from ..utils import (
    determine_ext,
    get_element_html_by_class,
    extract_attributes,
    unescapeHTML,
    unified_timestamp
)

class MicrosoftIE(InfoExtractor):
    _VALID_URL = r'https?://(?:www\.)?microsoft\.com/(?P<locale>[^/]*?)/videoplayer/embed/(?P<id>[A-Za-z0-9]+)'
    _TESTS = [{
        'url': 'https://www.microsoft.com/en-us/videoplayer/embed/RWL07e',
        'info_dict': {
            'id': 'RWL07e',
            'ext': 'mp4',
            'title': 'Microsoft for Public Health and Social Services',
            'timestamp': 1631658316
        }
    }]

    def _real_extract(self, url):
        video_id = self._match_id(url)
        webpage = self._download_webpage(url, video_id)
        
        shim_url = 'https://prod-video-cms-rt-microsoft-com.akamaized.net/vhs/api/videos/{0}'.format(video_id)
        
        metadata = self._download_json(shim_url, video_id)
        
        formats, subs = [], {}
        
        for locale, caption in metadata.get('captions', {}).items():
            lang = self._search_regex(r'(?P<lang>.*?)-.*', locale, 'lang')
            subs.setdefault(lang, []).append({
                'url': caption.get('url'),
                'ext': 'ttml',
                'name': locale
            })
        
        streams = metadata.get('streams', {})
        
        for stream_name, stream in streams.items():
            try:
                stream_url = stream['url']
            except KeyError:
                continue
            
            stream_formats, stream_subs = [], {}
            generic_match = re.fullmatch(r'(?P<codec>[^_]+)_(?P<width>\d+)_(?P<height>\d+)_(?P<bitrate>\d+)kbps', stream_name)
            if stream_name == 'apple_HTTP_Live_Streaming':
                stream_formats, stream_subs = self._extract_m3u8_formats_and_subtitles(
                    stream_url, video_id, 'hls')
            elif stream_name == 'mPEG_DASH':
                stream_formats, stream_subs = self._extract_mpd_formats_and_subtitles(
                    stream_url, video_id, 'dash')
            elif stream_name == 'smooth_Streaming':
                pass
                #stream_formats, stream_subs = self._extract_ism_formats_and_subtitles(
                    #stream_url, video_id, ism_id='mss', fatal=False)
            else:
                codec = 'unknown'
                width = height = 0
                if generic_match is not None:
                    codec = generic_match.group('codec')
                    width = generic_match.group('width')
                    height = generic_match.group('height')
                width = stream.get('widthPixels', width)
                height = stream.get('heightPixels', width)
                
                new_format = {
                    'url': stream_url,
                    'format_id': codec
                }
                
                if codec != 'unknown':
                    new_format['vcodec'] = codec
                
                if width > 0:
                    new_format['width'] = width
                if height > 0:
                    new_format['height'] = height
                
                ext = determine_ext(stream_url, '')
                if ext:
                    new_format['format_id'] = ext + '_' + new_format['format_id']
                audio_type = stream.get('audioType')
                if audio_type:
                    new_format['format_id'] += '_' + audio_type
                    new_format['acodec'] = audio_type
                
                bitrate = stream.get('bitrateBps', 0)
                if bitrate > 0:
                    new_format['vbr'] = bitrate
                
                fps = stream.get('frameRateFps', 0)
                if fps > 0:
                    new_format['fps'] = fps
                
                stream_formats.append(new_format)
            formats.extend(stream_formats)
            subs = self._merge_subtitles(subs, stream_subs)
        
        thumbnails = []
        for pref, (thumbnail_size, thumbnail) in enumerate(metadata.get('snippet').get('thumbnails').items()):
            thumbnail_entry = {
                'id': f'{video_id}_{thumbnail_size}',
                'url': thumbnail.get('url'),
                'preference': pref
            }
            if thumbnail.get('width') > 0:
                thumbnail_entry['width'] = thumbnail.get('width')
            if thumbnail.get('height') > 0:
                thumbnail_entry['height'] = thumbnail.get('height')
            thumbnails.append(thumbnail_entry)
        
        url_lang = self._match_valid_url(url).group('locale')
        for format in formats:
            lang = format.get('language')
            if lang == url_lang:
                format['language_preference'] = 10
            elif lang and lang.startswith('dau-') or 'Descriptive_Audio' in format['format_id']:
                # Put described audio at the beginning of the list, so that it
                # isn't chosen by default, as most people won't want it.
                format['preference'] = -2
        
        self._sort_formats(formats)
        
        print(unified_timestamp(metadata.get('snippet').get('activeStartDate')))

        return {
            'id': video_id,
            'title': metadata.get('snippet').get('title'),
            'formats': formats,
            'subtitles': subs,
            'thumbnails': thumbnails,
            'timestamp': unified_timestamp(metadata.get('snippet').get('activeStartDate'))
        }
