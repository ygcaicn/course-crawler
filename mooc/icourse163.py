# -*- coding: utf-8 -*-
"""中国大学MOOC"""

import time
from .utils import *
import json

CANDY = Crawler()
CONFIG = {}
FILES = {}


def get_summary(url):
    """从课程主页面获取信息"""
    res = CANDY.get(url)
    cookie_csrf = res.cookies.get('NTESSTUDYSI')
    res_t = res.text

    term_id = re.search(r'termId : "(\d+)"', res_t).group(1)
    names = re.findall(r'name:"(.+)"', res_t)

    dir_name = course_dir(*names[:2])

    print(dir_name)
    return term_id, dir_name, cookie_csrf


def parse_resource(resource):
    """解析资源地址和下载资源"""
    post_data = {'callCount': '1', 'scriptSessionId': '${scriptSessionId}190',
                 'httpSessionId': '5531d06316b34b9486a6891710115ebc', 'c0-scriptName': 'CourseBean',
                 'c0-methodName': 'getLessonUnitLearnVo', 'c0-id': '0', 'c0-param0': 'number:' + resource.meta[0],
                 'c0-param1': 'number:' + resource.meta[1], 'c0-param2': 'number:0',
                 'c0-param3': 'number:' + resource.meta[2], 'batchId': str(int(time.time()) * 1000)}
    res = CANDY.post('https://www.icourse163.org/dwr/call/plaincall/CourseBean.getLessonUnitLearnVo.dwr',
                     data=post_data).text


    file_name = resource.file_name
    if resource.type == 'Video':
        post_data = {'bizId': resource.meta[2],
                     'bizType': '1',
                     'contentType': '1'}
        url = 'https://www.icourse163.org/web/j/resourceRpcBean.getResourceToken.rpc?csrfKey={}'.format(CONFIG['_cookie_csrf'])
        res = CANDY.post(url,data=post_data).text
        res_json = json.loads(res)
        if res_json.get('code', -1) != 0:
            print('get signature error.')
            return
        sig = res_json['result']['videoSignDto']['signature']

        url = 'https://vod.study.163.com/eds/api/v1/vod/video?videoId={}&signature={}&clientType=1'.format(resource.meta[0], sig)
        res = CANDY.get(url).text
        res_json = json.loads(res)
        url = res_json['result']['videos'][-1]['videoUrl']
        name = res_json['result']['name']
        FILES['video'].write_string('{}\t{}'.format(name,url))
        res_print('{}\t{}'.format(name, url))


        if not CONFIG['sub']:
            return
        subtitles = re.findall(r'name="(.+)";.*url="(.*?)"', res)
        WORK_DIR.change('Videos')
        for subtitle in subtitles:
            if len(subtitles) == 1:
                sub_name = file_name + '.srt'
            else:
                subtitle_lang = subtitle[0].encode('utf_8').decode('unicode_escape')
                sub_name = file_name + '_' + subtitle_lang + '.srt'
            res_print(sub_name)
            CANDY.download_bin(subtitle[1], WORK_DIR.file(sub_name))

    elif resource.type == 'Document':
        if WORK_DIR.exist(file_name + '.pdf'):
            return
        pdf_url = re.search(r'textOrigUrl:"(.*?)"', res).group(1)
        res_print(file_name + '.pdf')
        CANDY.download_bin(pdf_url, WORK_DIR.file(file_name + '.pdf'))

    elif resource.type == 'Rich':
        if WORK_DIR.exist(file_name + '.html'):
            return
        text = re.search(r'htmlContent:"(.*)",id', res.encode('utf_8').decode('unicode_escape'), re.S).group(1)
        res_print(file_name + '.html')
        with open(WORK_DIR.file(file_name + '.html'), 'w', encoding='utf_8') as file:
            file.write(text)


def get_resource(term_id):
    """获取各种资源"""

    outline = Outline()
    counter = Counter()

    video_list = []
    pdf_list = []
    rich_text_list = []

    post_data = {'callCount': '1', 'scriptSessionId': '${scriptSessionId}190', 'c0-scriptName': 'CourseBean',
                 'c0-methodName': 'getMocTermDto', 'c0-id': '0', 'c0-param0': 'number:' + term_id,
                 'c0-param1': 'number:0', 'c0-param2': 'boolean:true', 'batchId': str(int(time.time()) * 1000)}
    res = CANDY.post('https://www.icourse163.org/dwr/call/plaincall/CourseBean.getMocTermDto.dwr',
                     data=post_data).text.encode('utf_8').decode('unicode_escape')

    chapters = re.findall(r'homeworks=\w+;.+id=(\d+).+name="(.+)";', res)
    for chapter in chapters:
        counter.add(0)
        outline.write(chapter[1], counter, 0)

        lessons = re.findall(r'chapterId=' + chapter[0] + r'.+contentType=1.+id=(\d+).+name="(.+)".+test', res)
        for lesson in lessons:
            counter.add(1)
            outline.write(lesson[1], counter, 1)

            videos = re.findall(r'contentId=(\d+).+contentType=(1).+id=(\d+).+lessonId=' +
                                lesson[0] + r'.+name="(.+)"', res)
            for video in videos:
                counter.add(2)
                outline.write(video[3], counter, 2, sign='#')
                video_list.append(Video(counter, video[3], video))
            counter.reset()

            pdfs = re.findall(r'contentId=(\d+).+contentType=(3).+id=(\d+).+lessonId=' +
                              lesson[0] + r'.+name="(.+)"', res)
            for pdf in pdfs:
                counter.add(2)
                outline.write(pdf[3], counter, 2, sign='*')
                if CONFIG['doc']:
                    pdf_list.append(Document(counter, pdf[3], pdf))
            counter.reset()

            rich_text = re.findall(r'contentId=(\d+).+contentType=(4).+id=(\d+).+jsonContent=(.+?);.+lessonId=' +
                                   lesson[0] + r'.+name="(.+)"', res)
            for text in rich_text:
                counter.add(2)
                outline.write(text[4], counter, 2, sign='+')
                if CONFIG['text']:
                    rich_text_list.append(RichText(counter, text[4], text))
                if CONFIG['file']:
                    if text[3] != 'null' and text[3] != '""':
                        params = {'nosKey': re.search('nosKey":"(.+?)"', text[3]).group(1),
                                  'fileName': re.search('"fileName":"(.+?)"', text[3]).group(1)}
                        file_name = Resource.file_to_save(params['fileName'])
                        outline.write(file_name, counter, 2, sign='!')

                        WORK_DIR.change('Files')
                        res_print(params['fileName'])
                        file_name = '%s %s' % (counter, file_name)
                        CANDY.download_bin('https://www.icourse163.org/course/attachment.htm',
                                           WORK_DIR.file(file_name), params=params)
            counter.reset()

    if video_list:
        rename = WORK_DIR.file('Names.txt') if CONFIG['rename'] else False
        WORK_DIR.change('Videos')
        if CONFIG['dpl']:
            playlist = Playlist()
            parse_res_list(video_list, rename, parse_resource, playlist.write)
        else:
            parse_res_list(video_list, rename, parse_resource)
    if pdf_list:
        WORK_DIR.change('PDFs')
        parse_res_list(pdf_list, None, parse_resource)
    if rich_text_list:
        WORK_DIR.change('Texts')
        parse_res_list(rich_text_list, None, parse_resource)


def start(url, config):
    """调用接口函数"""

    global WORK_DIR

    CONFIG.update(config)
    term_id, dir_name, cookie_csrf = get_summary(url)
    CONFIG['_cookie_csrf'] = cookie_csrf

    WORK_DIR = WorkingDir(CONFIG['dir'], dir_name)
    WORK_DIR.change('Videos')
    FILES['renamer'] = Renamer(WORK_DIR.file('Rename.bat'))
    FILES['video'] = ClassicFile(WORK_DIR.file('Videos.txt'))

    get_resource(term_id)
