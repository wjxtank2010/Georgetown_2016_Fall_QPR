from __future__ import absolute_import
import os, cbor
import logging
import re
import string

import lxml.html
import lxml.html.clean
#import lxml.html.soupparser
#from BeautifulSoup import UnicodeDammit

#from streamcorpus_pipeline.emails import fix_emails
#from streamcorpus_pipeline.stages import Configured

logger = logging.getLogger(__name__)

encoding_re = re.compile(
    '''(?P<start_xml>([^<]|\n)*?\<\?xml[^>]*)'''
    '''(?P<encoding>encoding=.*?)(?P<remainder>(\s|\?\>)(.|\n)*)''',
    re.I)

# regex to identify all XML-like tags, including SCRIPT and STYLE tags
invisible = re.compile(
    # capture the visible text before the invisible part
    '''(?P<before>(.|\n)*?)'''
    # capture everything between SCRIPT and STYLE tags,
    '''(?P<invisible>(<script(.|\n)*?</script>|<style(.|\n)*?</style>'''
    # and also everything inside of XML-like tags, even if it
    # contains newlines
    '''|<(.|\n)*?>))''',
    # ignore case
    re.I)

def re_based_make_clean_visible(html):
    '''
    Takes an HTML-like binary string as input and returns a binary
    string of the same length with all tags replaced by whitespace.
    This also detects script and style tags, and replaces the text
    between them with whitespace.
    Pre-existing whitespace of any kind (newlines, tabs) is converted
    to single spaces ' ', which has the same byte length (and
    character length).
    Note: this does not change any characters like &rsquo; and &nbsp;,
    so taggers operating on this text must cope with such symbols.
    Converting them to some other character would change their byte
    length, even if equivalent from a character perspective.
    This is regex based, which can occassionally just hang...
    '''
    text = ''
    # Fix emails
    html = fix_emails(html)

    for m in invisible.finditer(html):
        text += m.group('before')
        text += ' ' * len(m.group('invisible'))

    # text better be >= original
    assert len(html) >= len(text), '%d !>= %d' % (len(html), len(text))

    # capture any characters after the last tag... such as newlines
    tail = len(html) - len(text)
    text += html[-tail:]

    # now they must be equal
    assert len(html) == len(text), '%d != %d' % (len(html), len(text))

    return text


def make_clean_visible(_html, tag_replacement_char=' '):
    '''
    Takes an HTML-like binary string as input and returns a binary
    string of the same length with all tags replaced by whitespace.
    This does not detect comments, style, script, link.  It also does
    do anything with HTML-escaped characters.  All of these are
    handled by the clean_html pre-cursor step.
    Pre-existing whitespace of any kind (newlines, tabs) is converted
    to single spaces ' ', which has the same byte length (and
    character length).
    This is a simple state machine iterator without regexes
    '''
    def non_tag_chars(html):
        n = 0
        while n < len(html):
            angle = html.find('<', n)
            if angle == -1:
                yield html[n:]
                n = len(html)
                break
            yield html[n:angle]
            n = angle

            while n < len(html):
                nl = html.find('\n', n)
                angle = html.find('>', n)
                if angle == -1:
                    yield ' ' * (len(html) - n)
                    n = len(html)
                    break
                elif nl == -1 or angle < nl:
                    yield ' ' * (angle + 1 - n)
                    n = angle + 1
                    break
                else:
                    yield ' ' * (nl - n) + '\n'
                    n = nl + 1
                    # do not break

    # Protect emails by substituting with unique key
    #_html = fix_emails(_html)

    #Strip tags with previous logic
    non_tag = ''.join(non_tag_chars(_html))

    return non_tag

def drop_invalid_and_upper_utf8_chars(possibly_invalid_string):
    '''Clean unexpected Unicode characters, including non-BMP.
    Returns a copy of `possibly_invalid_string` with the following
    replaced by space (U+0020): ASCII control characters other than
    tab, carriage return, and newline; reserved code points for
    surrogate pairs; invalid characters U+FFFE and U+FFFF; and
    supplementary characters U+10000 and higher.
    :param unicode possibly_invalid_string: string to clean
    :return: cleaned string
    :returntype: :class:`unicode`
    '''
    return re.sub(ur'[^\t\r\n\u0020-\ud7ff\ue000-\ufffd]', u' ',
                  possibly_invalid_string)

def make_clean_html(raw, stream_item=None):
    '''Get a clean text representation of presumed HTML.
    Treat `raw` as though it is HTML, even if we have no idea what it
    really is, and attempt to get a properly formatted HTML document
    with all HTML-escaped characters converted to their unicode.
    :param str raw: raw text to clean up
    :param stream_item: optional stream item with encoding metadata
    :type stream_item: :class:`streamcorpus.StreamItem`
    :returns: UTF-8-encoded byte string of cleaned HTML text
    :returntype: :class:`str`
    '''
    # Fix emails by protecting the <,> from HTML
    #raw = fix_emails(raw)

    if stream_item and stream_item.body and stream_item.body.encoding:
        # if we know an encoding, then attempt to use it
        try:
            raw_decoded = raw.decode(stream_item.body.encoding)
        except:
            raw_decoded = raw
    else:
        raw_decoded = raw

    # default attempt uses vanilla lxml.html
    try:
        root = lxml.html.document_fromstring(raw_decoded)
    except Exception as e:
        # if 'with encoding declaration' in str(exc):
        #     root = lxml.html.document_fromstring(raw)
        # else:
        return ""
    # if that worked, then we will be able to generate a
    # valid HTML string
    fixed_html = lxml.html.tostring(root, encoding=unicode)

    # remove any ^M characters
    fixed_html = fixed_html.replace('\r', ' ')

    # We drop utf8 characters that are above 0xFFFF as
    # Lingpipe seems to be doing the wrong thing with them.
    fixed_html = drop_invalid_and_upper_utf8_chars(fixed_html)

    # construct a Cleaner that removes any ``<script>`` tags,
    # Javascript, like an ``onclick`` attribute, comments, style
    # tags or attributes, ``<link>`` tags
    cleaner = lxml.html.clean.Cleaner(
        scripts=True, javascript=True,
        comments=True,
        # do not remove <html> <head> <title> etc
        page_structure=True,
        meta=True,
        style=True, links=False)

    # now get the really sanitized HTML
    _clean_html = cleaner.clean_html(fixed_html)

    # generate pretty HTML in utf-8
    _clean_html = lxml.html.tostring(
        lxml.html.document_fromstring(_clean_html),
        method='html', encoding='utf-8',
        pretty_print=True,
        # include_meta_content_type=True
        )

    return _clean_html

# count = 0
# for filename in os.listdir('./tweets_unreduced/'):
#     fh = open('./tweets_unreduced/' + filename,'rb')
#     dh = open('./tweets_html_escape_moderate/' + filename, 'w')
#     dict = cbor.loads(fh.read())
#     for item in dict:
# 	if not 'text' in item:
# 		continue
#         if not 'key' in item:
# 		continue
# 	string = item['text']
# 	if not string == '' and not item['key']=='':
#         	escape_string = string#make_clean_html(string)
# 		#escape_string = make_clean_visible(escape_string)
# 		dh.write(('<DOC>\n<DOCNO>%s</DOCNO>\n<TEXT>\n%s\n</TEXT>\n</DOC>\n'%(item['key'].encode('utf-8'),escape_string)))
#         	print item['key']
#     fh.close()
#     dh.close()
#     count += 1



