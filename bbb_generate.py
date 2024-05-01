#! /usr/bin/python3
# -*- coding: utf-8 -*-
#--------------------------------------------------------------------------------------------------
# Generate HTML files from article files
#
# Copyright 2024 Mikio Hirabayashi
# Licensed under the Apache License, Version 2.0 (the "License"); you may not use this file
# except in compliance with the License.  You may obtain a copy of the License at
#     https://www.apache.org/licenses/LICENSE-2.0
# Unless required by applicable law or agreed to in writing, software distributed under the
# License is distributed on an "AS IS" BASIS, WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND,
# either express or implied.  See the License for the specific language governing permissions
# and limitations under the License.
#--------------------------------------------------------------------------------------------------

import argparse
import collections
import html
import logging
import os
import re
import shutil
import sys
import time
import urllib
import urllib.parse


MAIN_HEADER_TEXT = """
<?xml version="1.0" encoding="UTF-8"?>
<html xmlns="http://www.w3.org/1999/xhtml" lang="{lang}">
<head>
<title>{page_title}</title>
<link rel="stylesheet" href="{style_file}"/>
<script type="text/javascript" src="{script_file}"></script>
<meta name="generator" content="BikiBikiBob"/>
<meta name="author" content="{author}"/>
</head>
<body onload="main();">
<div class="site_title_area">
<h1><a href="{site_url}">{site_title}</a></h1>
<div class="subtitle">{site_subtitle}</div>
</div>
"""
MAIN_FOOTER_TEXT = """
</body>
</html>
"""


# Prepares the logger.
log_format = "%(levelname)s\t%(message)s"
logging.basicConfig(format=log_format, stream=sys.stderr)
logger = logging.getLogger(sys.argv[0])
logger.setLevel(logging.INFO)


# Main routine
def main(argv):
  ap = argparse.ArgumentParser(
    prog="bbb_generate.py", description="BBB HTML generator",
    formatter_class=argparse.RawDescriptionHelpFormatter)
  ap.add_argument("--conf", default="bbb.conf")
  ap.add_argument("articles", nargs="*")
  args = ap.parse_args(argv)
  conf_path = args.conf
  focus_names = args.articles
  start_time = time.time()
  logger.info("Process started: conf={}".format(conf_path))
  config = ReadConfig(conf_path)
  logger.info("Config: {}".format(str(config)))
  articles = ReadInputDir(config, focus_names)
  if not articles:
    raise ValueError("no input files")
  index = {}
  count_index = collections.defaultdict(int)
  for article in articles:
    title = article.get("title")
    if not title: continue
    title = title.lower()
    count = count_index[title] + 1
    if count > 1:
      title = title + " ({})".format(count)
    if title not in index:
      index[title] = article
    count_index[title] = count
  MakeOutputDir(config)
  for article in articles:
    MakeArticle(config, articles, index, article)
  logger.info("Process done: elapsed_time={:.2f}s".format(time.time() - start_time))


def ReadConfig(conf_path):
  config = {}
  with open(conf_path) as input_file:
    for line in input_file:
      line = line.strip()
      match = re.search(r"^([-_a-zA-Z0-9]+) *: *([^ ].*)$", line)
      if not match: continue
      name = match.group(1).strip()
      value = match.group(2).strip()
      if name:
        config[name] = value
  base_dir = os.path.dirname(os.path.realpath(conf_path))
  config["input_dir"] = os.path.join(base_dir, config["input_dir"])
  config["output_dir"] = os.path.join(base_dir, config["output_dir"])
  config["script_file"] = os.path.join(base_dir, config["script_file"])
  config["style_file"] = os.path.join(base_dir, config["style_file"])
  if not config["title"]: raise ValueError("empty title in the config")
  if not config["author"]: raise ValueError("empty author in the config")
  return config


def ReadArticleMetadata(path):
  title = ""
  date = ""
  with open(path) as input_file:
    for line in input_file:
      line = line.rstrip()
      match = re.search(r"^@title +([^\s].*)$", line)
      if match and not title:
        title = match.group(1).strip()
      match = re.search(r"^@date +([^\s].*)$", line)
      if match and not date:
        date = match.group(1).strip()
  if title and not date:
    logger.warning("no date: {}".format(path))
  if date and not title:
    logger.warning("no title: {}".format(path))
  if (date and not re.fullmatch(r"\d{4}-\d{2}-\d{2}", date) and
      not re.fullmatch(r"\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2}", date)):
    logger.warning("invalid date format: {}: {}".format(path, date))
  article = {
    "path": path,
    "title": title,
    "date": date,
  }
  return article


def ReadInputDir(config, focus_names):
  input_dir = config["input_dir"]
  names = os.listdir(input_dir)
  focus_stem_set = set()
  for name in focus_names:
    stem = re.sub(r"\.art$", "", os.path.basename(name))
    if stem:
      focus_stem_set.add(stem)
  articles = []
  for name in names:
    if not name.endswith(".art"): continue
    stem = re.sub(r"\.art$", "", name)
    if focus_stem_set and stem not in focus_stem_set: continue
    path = os.path.join(input_dir, name)
    article = ReadArticleMetadata(path)
    articles.append(article)
  return sorted(articles, key=lambda x: x["path"])


def MakeOutputDir(config):
  output_dir = config["output_dir"]
  os.makedirs(output_dir, exist_ok=True)
  in_script_path = config["script_file"]
  out_script_path = os.path.join(output_dir, os.path.basename(in_script_path))
  shutil.copyfile(in_script_path, out_script_path)
  in_style_path = config["style_file"]
  out_style_path = os.path.join(output_dir, os.path.basename(in_style_path))
  shutil.copyfile(in_style_path, out_style_path)
  names = os.listdir(output_dir)
  for name in names:
    if not name.endswith(".xhtml"): continue
    path = os.path.join(output_dir, name)
    is_article = False
    is_empty = True
    with open(path) as input_file:
      for line in input_file:
        is_empty = False
        line = line.strip()
        if re.search(r'<meta .*name="generator".*content="BikiBikiBob".*/>', line):
          is_article = True
    if is_article or is_empty:
      os.remove(path)


def OrganizeSections(lines):
  sections = []
  section_break = True
  i = 0
  while i < len(lines):
    line = lines[i]
    i += 1
    if not line:
      section_break = True
      continue
    match = re.search(r"^>\|\|$", line)
    if match:
      pre_lines = []
      while i < len(lines):
        line = lines[i]
        i += 1
        if re.search(r"^\|\|<$", line):
          break
        pre_lines.append(line)
      section = {
        "type": "pre",
        "lines": pre_lines,
      }
      sections.append(section)
      section_break = True
      continue
    match = re.search(r"^-+ ", line)
    if match:
      ul_lines = [line]
      while i < len(lines):
        line = lines[i]
        if not re.search(r"^-+ ", line):
          break
        i += 1
        ul_lines.append(line)
      section = {
        "type": "ul",
        "lines": ul_lines,
      }
      sections.append(section)
      section_break = True
      continue
    match = re.search(r"^\|", line)
    if match:
      table_lines = [line]
      while i < len(lines):
        line = lines[i]
        if not re.search(r"^\|", line):
          break
        i += 1
        table_lines.append(line)
      section = {
        "type": "table",
        "lines": table_lines,
      }
      sections.append(section)
      section_break = True
      continue
    match = re.search(r"^@[a-z]+ ", line)
    if match:
      section = {
        "type": "meta",
        "lines": [line]
      }
      sections.append(section)
      section_break = True
      continue
    match = re.search(r"^\*+ ", line)
    if match:
      h_lines = [line]
      section = {
        "type": "h",
        "lines": h_lines,
      }
      sections.append(section)
      section_break = True
      continue

    if not section_break and sections and sections[-1]["type"] == "p":
      sections[-1]["lines"].append(line)
      continue
    p_lines = [line]
    section = {
      "type": "p",
      "lines": p_lines,
    }
    sections.append(section)
    section_break = False
  return sections


def GetOutputFilename(name):
  return re.sub(r"\.art$", r".xhtml", name)


def EscapeHeaderId(expr):
  if expr is None:
    return ""
  expr = expr.lower()
  expr = re.sub(r"\s+", "_", expr)[:64]
  return expr


def ToBool(expr):
  if not expr: return False
  return expr.lower() in ["true", "yes", "1"]


def MakeArticle(config, articles, index, article):
  article_path = article["path"]
  output_dir = config["output_dir"]
  in_article_name = os.path.basename(article_path)
  out_article_name = GetOutputFilename(in_article_name)
  out_article_path = os.path.join(output_dir, out_article_name)
  if os.path.exists(out_article_path):
    raise FileExistsError("cannot overwrite an article: " + out_article_path)
  logger.info("Creating article: {} -> {}".format(article_path, out_article_path))
  input_lines = []
  with open(article_path) as input_file:
    for line in input_file:
      line = re.sub(r"\s", " ", line.rstrip())
      input_lines.append(line)
  sections = OrganizeSections(input_lines)
  with open(out_article_path, "w") as output_file:
    PrintArticle(config, articles, index, article, sections, output_file)


def esc(expr):
  if expr is None:
    return ""
  return html.escape(str(expr), True)


def PrintArticle(config, articles, index, article, sections, output_file):
  def P(*args, end="\n"):
    esc_args = []
    for arg in args[1:]:
      if isinstance(arg, str):
        arg = esc(arg)
      esc_args.append(arg)
    print(args[0].format(*esc_args), end=end, file=output_file)
  title = article.get("title") or ""
  date = article.get("date") or ""
  page_title = config["title"]
  if title:
    page_title = page_title + ": " + title
  site_url = "./"
  main_header = MAIN_HEADER_TEXT.format(
    lang=esc(config["language"]),
    author=esc(config["author"]),
    style_file=esc(os.path.basename(config["style_file"])),
    script_file=esc(os.path.basename(config["script_file"])),
    page_title=esc(page_title),
    site_title=esc(config["title"]),
    site_subtitle=esc(config["subtitle"]),
    site_url=esc(site_url))
  print(main_header.strip(), file=output_file)
  id_count_index = collections.defaultdict(int)
  if title or date:
    P('<div class="page_title_area">')
    if title:
      page_url = os.path.basename(article["path"])
      page_url = GetOutputFilename(page_url)
      P('<h2><a href="{}">{}</a></h2>', urllib.parse.quote(page_url), title)
    if date:
      P('<div class="date">{}</div>', date)
    P('</div>')
  for section in sections:
    elem_type = section["type"]
    lines = section["lines"]
    if elem_type == "h":
      for line in lines:
        match = re.search("^(\*+) +(.*)$", line)
        level = min(len(match.group(1)), 3)
        text = match.group(2)
        elem = "h{:d}".format(level + 2)
        head_id = EscapeHeaderId(text)
        id_count = id_count_index[head_id]
        id_count += 1
        if id_count > 1:
          head_id = head_id + "__{:d}".format(id_count)
        id_count_index[head_id] = id_count
        P('<{} id="{}">', elem, head_id, end="")
        P('{}', text, end="")
        P('</' + elem + '>')
    if elem_type == "ul":
      P('<ul>')
      for line in lines:
        match = re.search("^(-+) +(.*)$", line)
        level = min(len(match.group(1)), 3)
        text = match.group(2)
        P('<li class="l{:d}">', level, end="")
        PrintText(P, index, text)
        P('</li>')
      P('</ul>')
    if elem_type == "table":
      P('<table>')
      for line in lines:
        P('<tr>')
        line = re.sub(r"^\|", "", line)
        line = re.sub(r"\[\[([^\]]+)\|([^\]]+)\]\]", r"[[\1{{_VERT_}}\2]]", line)
        fields = line.split("|")
        for field in fields:
          field = re.sub(r"{{_VERT_}}", "|", field)
          P('<td>', end="")
          PrintText(P, index, field)
          P('</td>', end="")
        P('</tr>')
      P('</table>')
    if elem_type == "p":
      P('<p>', end="")
      for i, line in enumerate(lines):
        PrintText(P, index, line)
        if i < len(lines) - 1:
          P('<br/>')
      P('</p>')
    if elem_type == "pre":
      P('<pre>', end="")
      for i, line in enumerate(lines):
        P('{}', line)
      P('</pre>')
    if elem_type == "meta":
      match = re.search("^@([a-z]+) +(.*)$", lines[0])
      name = match.group(1)
      params = match.group(2)
      if name == "image":
        PrintImage(P, params)
      elif name == "video":
        PrintVideo(P, params)
      elif name == "youtube":
        PrintYoutube(P, params)
      elif name == "index":
        PrintIndex(P, articles, params)
      elif name not in ["title", "date"]:
        logger.warning("unknown meta directive: {}".format(name))
  print(MAIN_FOOTER_TEXT.strip(), file=output_file)


def PrintRichPhrase(P, index, text):
  text = re.sub(r"^\[(.*)\]$", "\1", text)
  match = re.fullmatch(r"\*(.*)\*", text)
  if match:
    P('<b>{}</b>', match.group(1), end="")
    return
  match = re.fullmatch(r"/(.*)/", text)
  if match:
    P('<i>{}</i>', match.group(1), end="")
    return
  match = re.fullmatch(r"{(.*)}", text)
  if match:
    P('<kbd>{}</kbd>', match.group(1), end="")
    return
  match = re.fullmatch(r"(.*?)\|(.*)", text)
  if match:
    face = match.group(1).strip()
    dest = match.group(2).strip()
  else:
    face = text.strip()
    dest = text.strip()
  if re.search(r"^https?://", dest):
    dest_url = dest
  else:
    match = re.search(r"(^[^#]+)#(.+)$", dest)
    if match:
      dest_title = match.group(1)
      dest_fragment = match.group(2)
    else:
      dest_title = dest
      dest_fragment = ""
    dest_article = index.get(dest_title.lower())
    if dest_article:
      dest_url = GetOutputFilename(
        "./" + urllib.parse.quote(os.path.basename(dest_article["path"])))
      if dest_fragment:
        dest_url = dest_url + "#" + EscapeHeaderId(dest_fragment)
    else:
      dest_url = ""
  if not dest_url:
    logger.warning("invalid hyperlink: {}: {}".format(face, dest))
  P('<a href="{}">{}</a>', dest_url, face, end="")


def PrintText(P, index, text):
  text = text.strip()
  text = re.sub(r"\[\*(.*?)\*\]", r"[[*\1*]]", text)
  text = re.sub(r"\[/(.*?)/\]", r"[[/\1/]]", text)
  text = re.sub(r"\[{(.*?)}\]", r"[[{\1}]]", text)
  while True:
    match = re.search(r"(.*?)\[\[(.*?)\]\](.*)", text)
    if match:
      P('{}', match.group(1), end="")
      PrintRichPhrase(P, index, match.group(2))
      text = match.group(3)
    else:
      P('{}', text, end="")
      break


def PrintImage(P, params):
  P('<div class="image_area">')
  columns = params.split("|")
  for column in columns:
    column = column.strip()
    attrs = {}
    while True:
      match = re.search(r"^(.*)\[([a-z]+?)=(.*?)\](.*)$", column)
      if match:
        attr_name = match.group(2).strip()
        attr_value = match.group(3).strip()
        attrs[attr_name] = attr_value
        column = (match.group(1) + " " + match.group(4)).strip()
      else:
        break
    url = column
    caption = attrs.get("caption")
    width = attrs.get("width")
    styles = []
    if width:
      num_width = re.sub(r"[^0-9]", "", width)
      if num_width:
        styles.append("max-width: {}%".format(num_width))
    P('<span class="image_cell">', end="")
    if caption:
      P('<span class="image_caption">{}</span>', caption, end="")
    P('<a href="{}">', url, end="")
    P('<img src="{}" class="img{}" style="{}"/>', url, len(columns), ";".join(styles), end="")
    P('</a>', end="")
    P('</span>')
  P('</div>')
  

def PrintVideo(P, params):
  P('<div class="video_area">')
  columns = params.split("|")
  for column in columns:
    column = column.strip()
    attrs = {}
    while True:
      match = re.search(r"^(.*)\[([a-z]+?)=(.*?)\](.*)$", column)
      if match:
        attr_name = match.group(2).strip()
        attr_value = match.group(3).strip()
        attrs[attr_name] = attr_value
        column = (match.group(1) + " " + match.group(4)).strip()
      else:
        break
    url = column
    caption = attrs.get("caption")
    width = attrs.get("width")
    styles = []
    if width:
      num_width = re.sub(r"[^0-9]", "", width)
      if num_width:
        styles.append("max-width: {}%".format(num_width))
    P('<span class="video_cell">', end="")
    if caption:
      P('<span class="video_caption">{}</span>', caption, end="")
    P('<video src="{}" controls="controls" preload="metadata" class="video{}" style="{}"/>',
      url, len(columns), ";".join(styles), end="")
    P('</span>')
  P('</div>')


def PrintYoutube(P, params):
  P('<div class="youtube_area">')
  columns = params.split("|")
  for column in columns:
    column = column.strip()
    attrs = {}
    while True:
      match = re.search(r"^(.*)\[([a-z]+?)=(.*?)\](.*)$", column)
      if match:
        attr_name = match.group(2).strip()
        attr_value = match.group(3).strip()
        attrs[attr_name] = attr_value
        column = (match.group(1) + " " + match.group(4)).strip()
      else:
        break
    url = column
    caption = attrs.get("caption")
    width = attrs.get("width")
    styles = []
    if width:
      num_width = re.sub(r"[^0-9]", "", width)
      if num_width:
        styles.append("width: {}%".format(num_width))
    P('<span class="youtube_cell">', end="")
    if caption:
      P('<span class="youtube_caption">{}</span>', caption, end="")

    video_id = ""
    match = re.search(r"[?&]v=([_a-zA-Z0-9]+)([&#]|$)", url)
    if match:
      video_id = match.group(1)
    else:
      video_id = re.sub(r"[^_a-zA-Z0-9]", "", url)[:16]
    url = "https://www.youtube-nocookie.com/embed/" + video_id
    P('<iframe src="{}" frameborder="0" class="youtube{}" style="{}"></iframe>',
      url, len(columns), ";".join(styles), end="")
    P('</span>')
  P('</div>')


def PrintIndex(P, articles, params):
  P('<div class="index_area">')
  attrs = {}
  while True:
    match = re.search(r"^(.*)\[([a-z]+?)=(.*?)\](.*)$", params)
    if match:
      attr_name = match.group(2).strip()
      attr_value = match.group(3).strip()
      attrs[attr_name] = attr_value
      params = (match.group(1) + " " + match.group(4)).strip()
    else:
      break
  order = attrs.get("order")
  reverse = ToBool(attrs.get("reverse"))
  max_num = int(attrs.get("max") or 0)
  if not order or order == "filename":
    articles = sorted(articles, key=lambda x: x["path"], reverse=reverse)
  elif order == "date":
    articles = [x for x in articles if x.get("date")]
    articles = sorted(articles, key=lambda x: x["date"], reverse=reverse)
  elif order == "title":
    articles = [x for x in articles if x.get("title")]
    articles = sorted(articles, key=lambda x: x["title"], reverse=reverse)
  if max_num > 0:
    articles = articles[:max_num]
  P('<ul>')
  for article in articles:
    path = article.get("path")
    name = os.path.basename(path)
    url = "./" + GetOutputFilename(name)
    title = article.get("title")
    if not title:
      title = re.sub(r"\.art$", "", os.path.basename(name))
    date = article.get("date")
    P('<li>', end="")
    P('<a href="{}">{}</a>', url, title, end="")
    if date:
      P(' <span class="attrdate">({})</span>', date, end="")
    P('</li>')
  P('</ul>')
  P('</div>')


if __name__ == "__main__":
  sys.exit(main(sys.argv[1:]))


# END OF FILE
