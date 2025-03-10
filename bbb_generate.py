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
import urllib.request


MAIN_HEADER_TEXT = r"""
<?xml version="1.0" encoding="UTF-8"?>
<html xmlns="http://www.w3.org/1999/xhtml" lang="{lang}">
<head prefix="og: http://ogp.me/ns#">
<meta charset="UTF-8"/>
<meta name="viewport" content="width=device-width,initial-scale=1"/>
<meta name="generator" content="BikiBikiBob"/>
{extra_head_lines}
<title>{page_title}</title>
<link rel="stylesheet" href="{style_file}"/>
<script type="text/javascript" src="{script_file}"></script>
</head>
<body onload="main();">{extra_body_header_lines}
<div class="site_title_area {site_title_subclass}">
<h1><a href="{site_url}">{site_title}</a></h1>{extra_site_title}
</div>
"""
MAIN_FOOTER_TEXT = r"""
{extra_body_footer_lines}</body>
</html>
"""
TWITTER_BUTTON_TEXT = r"""
<span class="share_button" style="display:inline-box;">
<a href="https://twitter.com/share?ref_src=twsrc%5Etfw" class="twitter-share-button" data-size="large" data-show-count="false"></a>
</span>
<script src="https://platform.twitter.com/widgets.js" charset="utf-8" async="async"></script>
"""
LINE_BUTTON_TEXT = r"""
<span class="share_button" style="display:inline-box;">
<div class="line-it-button" data-lang="{lang}" data-type="share-b" data-env="REAL" data-url="{url}" data-color="default" data-size="true" data-count="false" data-ver="3" style="display: none;"></div>
</span>
<script src="https://www.line-website.com/social-plugins/js/thirdparty/loader.min.js" async="async" defer="defer"></script>
"""
FACEBOOK_BUTTON_TEXT = r"""
<span class="share_button" style="display:inline-box;line-height:11px;"><div id="fb-root"></div><div class="fb-share-button" data-layout="box_count" data-href="{url}"></div></span>
<script crossorigin="anonymous" src="https://connect.facebook.net/{locale}/sdk.js#xfbml=1&amp;version=v19.0" nonce="fxDGtCJR" async="async" defer="defer"></script>
"""
HATENA_BUTTON_TEXT = r"""
<span class="share_button" style="display:inline-box;"><a href="https://b.hatena.ne.jp/entry/" class="hatena-bookmark-button" data-hatena-bookmark-layout="vertical-normal" data-hatena-bookmark-lang="{lang}"><img src="https://b.st-hatena.com/images/v4/public/entry-button/button-only@2x.png" loading="lazy" width="20" height="20" style="border: none;"/></a></span>
<script type="text/javascript" src="https://b.st-hatena.com/js/bookmark_button.js" charset="utf-8" async="async" defer="defer"></script>
"""
MAX_DESCRIPTION_WIDTH = 160
MAX_HOARD_FILE_SIZE = 1024 * 1024 * 256
MIME_EXTS = {
  "application/octet-stream": "oct",
  "application/xhtml+xml": "xhtml",
  "application/xml": "xml",
  "text/html": "html",
  "text/xml": "xml",
  "text/csv": "csv",
  "text/plain": "txt",
  "image/jpeg": "jpg",
  "image/png": "png",
  "image/gif": "gif",
  "image/tiff": "tiff",
  "image/svg+xml": "svg",
  "image/heif": "heic",
  "video/mpeg": "mpg",
  "video/mp4": "mp4",
  "video/quicktime": "mov",
  "video/x-ms-wmv": "wmv",
  "video/x-msvideo": "avi",
}


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
  ap.add_argument("--hoard", action="store_true")
  ap.add_argument("articles", nargs="*")
  args = ap.parse_args(argv)
  conf_path = args.conf
  with_hoard = args.hoard
  focus_names = args.articles
  focus_stem_set = set()
  for name in focus_names:
    stem = re.sub(r"\.art$", "", os.path.basename(name))
    if stem:
      focus_stem_set.add(stem)
  start_time = time.time()
  logger.info("Process started: conf={}".format(conf_path))
  config = ReadConfig(conf_path, with_hoard)
  logger.info("Config: {}".format(str(config)))
  EnhanceConfig(config)
  articles = ReadInputDir(config, focus_stem_set)
  if not articles:
    raise ValueError("no input files")
  logger.info("Number of articles: {}".format(len(articles)))
  index = {}
  count_index = collections.defaultdict(int)
  for article in articles:
    esc_name = "filename:" + re.sub(r"\.art$", "", article["name"])
    index[esc_name] = article
    title = article.get("title")
    if title:
      title = title.lower()
      count = count_index[title] + 1
      if count > 1:
        title = title + " ({:d})".format(count)
      if title not in index:
        index[title] = article
      count_index[title] = count
  MakeOutputDir(config, focus_stem_set)
  if with_hoard:
    for article in articles:
      HoardDataAndRewriteArticle(config, article)
  for article in articles:
    MakeArticle(config, articles, index, article)
  if not focus_stem_set:
    MakeTocFile(config, articles)
  logger.info("Process done: elapsed_time={:.3f}s".format(time.time() - start_time))


def ReadConfig(conf_path, with_hoard):
  config = {}
  with open(conf_path) as input_file:
    for line in input_file:
      line = line.strip()
      match = re.search(r"^([-_a-zA-Z0-9]+) *: *([^ ].*)$", line)
      if not match: continue
      name = match.group(1).strip()
      value = match.group(2).strip()
      if name in ["extra_meta", "share_button", "hoard_target_url"]:
        if name not in config:
          config[name] = []
        config[name].append(value)
      elif name:
        config[name] = value
  base_dir = os.path.dirname(os.path.realpath(conf_path))
  config["base_dir"] = base_dir
  config["input_dir"] = os.path.realpath(os.path.join(base_dir, config["input_dir"]))
  if not os.path.isdir(config["input_dir"]): raise ValueError("input_dir is not a directory")
  config["output_dir"] = os.path.realpath(os.path.join(base_dir, config["output_dir"]))
  config["script_file"] = os.path.realpath(os.path.join(base_dir, config["script_file"]))
  if not os.path.isfile(config["script_file"]): raise ValueError("script_file is not a file")
  config["style_file"] = os.path.realpath(os.path.join(base_dir, config["style_file"]))
  if not os.path.isfile(config["style_file"]): raise ValueError("style_file is not a file")
  if not config["site_url"]: raise ValueError("empty site_url in the config")
  if not config["title"]: raise ValueError("empty title in the config")
  if not config["language"]: raise ValueError("empty language in the config")
  if with_hoard:
    if not config["hoard_target_url"]:
      raise ValueError("empty hoard_target_url")
    if not config["hoard_local_url"]: raise ValueError("empty hoard_local_url in the config")
    config["hoard_data_dir"] = os.path.realpath(os.path.join(base_dir, config["hoard_data_dir"]))
    if not os.path.isdir(config["hoard_data_dir"]):
      raise ValueError("hoard_data_dir is not a directory")
  return config


def EnhanceConfig(config):
  def ReadHTMLFile(name):
    path = os.path.join(config["base_dir"], name)
    lines = []
    with open(path) as input_file:
      for line in input_file:
        line = line.rstrip()
        if not line: continue
        lines.append(line)
    return lines
  extra_head_file = config.get("extra_head_file")
  if extra_head_file:
    config["extra_head_lines"] = ReadHTMLFile(extra_head_file)
  extra_body_header_file = config.get("extra_body_header_file")
  if extra_body_header_file:
    config["extra_body_header_lines"] = ReadHTMLFile(extra_body_header_file)
  extra_body_footer_file = config.get("extra_body_footer_file")
  if extra_body_header_file:
    config["extra_body_footer_lines"] = ReadHTMLFile(extra_body_footer_file)


def ReadArticleMetadata(path):
  title = ""
  date = ""
  tags = ""
  misc = ""
  desc = ""
  top_image = ""
  images = []
  with open(path) as input_file:
    end_pre_line = ""
    for line in input_file:
      line = line.rstrip()
      if end_pre_line:
        if line == end_pre_line:
          end_pre_line = ""
        continue
      else:
        match = re.search(r"^(>+)\|([a-z]*)\|$", line)
        if match:
          end_pre_line = "||" + ("<" * len(match.group(1)))
          continue
      match = re.search(r"^@title +([^\s].*)$", line)
      if match and not title:
        title = match.group(1).strip()
      match = re.search(r"^@date +([^\s].*)$", line)
      if match and not date:
        date = match.group(1).strip()
      match = re.search(r"^@tags +([^\s].*)$", line)
      if match and not tags:
        tags = match.group(1).strip()
      match = re.search(r"^@misc +(.*)$", line)
      if match and not misc:
        misc = match.group(1).strip()
      match = re.search(r"^@desc +([^\s].*)$", line)
      if match and not desc:
        desc = match.group(1).strip()
      match = re.search(r"^@image +(.*)$", line)
      if match:
        columns = match.group(1).split("|")
        for column in columns:
          attrs = ParseMetaParams(column)
          url = attrs[""]
          if url:
            images.append(url)
            if attrs.get("top") and not top_image:
              top_image = url
  if (date and not re.fullmatch(r"\d{4}/\d{2}/\d{2}", date) and
      not re.fullmatch(r"\d{4}/\d{2}/\d{2} \d{2}:\d{2}:\d{2}", date)):
    logger.warning("invalid date format: {}: {}".format(path, date))
  if not top_image and images:
    top_image = images[0]
  article = {
    "path": path,
    "title": title,
    "date": date,
    "tags": tags,
    "misc": misc,
    "desc": desc,
    "image": top_image,
  }
  return article


def ReadInputDir(config, focus_stem_set):
  input_dir = config["input_dir"]
  names = os.listdir(input_dir)
  articles = []
  for name in names:
    if name.startswith("."): continue
    if not name.endswith(".art"): continue
    stem = re.sub(r"\.art$", "", name)
    if focus_stem_set and stem not in focus_stem_set: continue
    path = os.path.join(input_dir, name)
    article = ReadArticleMetadata(path)
    article["name"] = name
    article["stem"] = stem
    articles.append(article)
  return sorted(articles, key=lambda x: x["path"])


def MakeOutputDir(config, focus_stem_set):
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
    stem = re.sub(r"\.xhtml$", "", name)
    if focus_stem_set and stem not in focus_stem_set: continue
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
    match = re.search(r"^(>+)\|([a-z]*)\|$", line)
    if match:
      end_line = "||" + ("<" * len(match.group(1)))
      pre_lines = []
      while i < len(lines):
        line = lines[i]
        i += 1
        if line == end_line:
          break
        pre_lines.append(line)
      section = {
        "type": "pre",
        "lines": pre_lines,
      }
      sections.append(section)
      section_break = True
      continue
    match = re.search(r"^[-+]+ ", line)
    if match:
      ul_lines = [line]
      while i < len(lines):
        line = lines[i]
        if not re.search(r"^[+-]+ ", line):
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
    match = re.search(r"^@[-_a-z]+( |$)", line)
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
    match = re.search(r"^-{2,5}$", line)
    if match:
      hr_lines = [line]
      section = {
        "type": "hr",
        "lines": hr_lines,
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


def CutTextByWidth(text, width):
  new_text = ""
  score = 0.0
  for c in text:
    cp = ord(c)
    if cp < 0x0200:
      score += 1.0
    elif cp < 0x3000:
      score += 1.5
    else:
      score += 2.0
    if score > width:
      new_text += "…"
      break
    new_text += c
  return new_text


def HoardDataAndRewriteArticle(config, article):
  article_path = article["path"]
  article_stem = article["stem"]
  target_urls = config["hoard_target_url"]
  local_url = config["hoard_local_url"]
  data_dir = config["hoard_data_dir"]
  input_lines = []
  with open(article_path) as input_file:
    for line in input_file:
      line = re.sub(r"\s", " ", line.rstrip())
      input_lines.append(line)
  article_modified = False
  output_lines = []
  count_data = 0
  for line in input_lines:
    line_modified = False
    match = re.search("^@(image|video) +(.*)$", line)
    if match:
      tag = match.group(1)
      params = match.group(2)
      columns = params.split("|")
      mod_columns = []
      for column in columns:
        column_modified = False
        attrs = ParseMetaParams(column)
        url = attrs[""]
        hit = False
        if not url.startswith(local_url):
          for target_url in target_urls:
            if re.search(target_url, url):
              hit = True
        if hit:
          logger.info("Fetcing data: {}: {}".format(article_stem, url))
          count_data += 1
          saved_filename = FetchDataByUrl(data_dir, article_stem, count_data, url)
          if saved_filename:
            new_url = re.sub(r"/[^/]+$", "/", local_url) + urllib.parse.quote(saved_filename)
            if CheckDataByUrl(new_url):
              if url == article.get("image"):
                article["image"] = new_url
              url = new_url
              column_modified = True
        if column_modified:
          column = "" + url
          for name, value in attrs.items():
            if not name: continue
            if value == True:
              column += " [{}]".format(name)
            else:
              column += " [{}={}]".format(name, value)
          line_modified = True
        mod_columns.append(column)
      if line_modified:
        line = "@" + tag + " " + " | ".join(mod_columns)
        article_modified = True
    output_lines.append(line)
  if article_modified:
    logger.info("Rewriting article: {}".format(article_path))
    with open(article_path, "w") as output_file:
      for line in output_lines:
        print(line, file=output_file)


def FetchDataByUrl(data_dir, article_stem, count_data, url):
  try:
    req = urllib.request.Request(url)
    with urllib.request.urlopen(req) as response:
      info = response.info()
      clen = info.get("Content-Length")
      if clen != None:
        clen = int(clen)
        if clen < 1:
          logger.info("Fetcing failed: empty data: {}: {}".format(article_stem, url))
          return None
        if clen > MAX_HOARD_FILE_SIZE:
          logger.info("Fetcing failed: too large: {}: {}: {}".format(article_stem, url, clen))
          return None
      ctype = info.get("Content-Type") or ""
      ctype = re.sub(r";.*", "", ctype).strip()
      ext = MIME_EXTS.get(ctype)
      if not ext:
        ext = re.sub(r"^[^/]+/", "", ctype)
        ext = re.sub(r".*\+/", "", ext)
        ext = re.sub(r"[^a-z0-9]", "", ext)
      if not ext:
        ext = "unknown"
      num_tries = 0
      while True:
        num_tries += 1
        if num_tries > 1:
          filename = "{}-{:03d}-{:03d}.{}".format(article_stem, count_data, num_tries, ext)
        else:
          filename = "{}-{:03d}.{}".format(article_stem, count_data, ext)
        path = os.path.join(data_dir, filename)
        if not os.path.exists(path): break
      with open(path, "wb") as output_file:
        total_size = 0
        while True:
          buf = response.read(8192)
          if len(buf) == 0: break
          total_size += len(buf)
          if total_size > MAX_HOARD_FILE_SIZE:
            logger.info("Fetcing failed: too large: {}: {}: {}".format(
              article_stem, url, total_size))
            os.remove(path)
            return None
          output_file.write(buf)
      return filename
  except urllib.error.URLError as e:
    logger.info("Fetcing failed: URLError: {}: {}: {}".format(article_stem, url, str(e)))
  except urllib.error.HTTPError as e:
    logger.info("Fetcing failed: HTTPError: {}: {}: {}".format(article_stem, url, str(e)))
  except Exception as e:
    logger.info("Fetcing failed: Exception: {}: {}: {}".format(article_stem, url, str(e)))
  return None


def CheckDataByUrl(url):
  try:
    req = urllib.request.Request(url)
    with urllib.request.urlopen(req) as response:
      info = response.info()
      clen = int(info.get("Content-Length") or 0)
      if clen < 1:
        logger.info("Checking failed: empty data: {}".format(url))
        return False
      return True
  except urllib.error.URLError as e:
    logger.info("Checking failed: URLError: {}: {}".format(url, str(e)))
  except urllib.error.HTTPError as e:
    logger.info("Checking failed: HTTPError: {}: {}".format(url, str(e)))
  except Exception as e:
    logger.info("Checking failed: Exception: {}: {}".format(url, str(e)))
  return False


def MakeArticle(config, articles, index, article):
  article_path = article["path"]
  output_dir = config["output_dir"]
  in_article_name = article["name"]
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


def NormalizeMetaText(text):
  return re.sub(r"\s+", " ", text).strip()


def UnescapeText(text, depth):
  if depth > 10:
    return text
  output = ""
  while True:
    idx = text.find("[")
    if idx >= 0:
      if idx > 0:
        output += text[:idx]
        text = text[idx:]
      match = re.search("^\[\|\|(.*?)\|\|\]", text)
      if match:
        output += match.group(1)
        text = text[match.end():]
        continue
      match = re.search("^\[\*(.*?)\*\]", text)
      if match:
        output += UnescapeText(match.group(1), depth + 1)
        text = text[match.end():]
        continue
      match = re.search("^\[/(.*?)/\]", text)
      if match:
        output += UnescapeText(match.group(1), depth + 1)
        text = text[match.end():]
        continue
      match = re.search("^\[_(.*?)_\]", text)
      if match:
        output += UnescapeText(match.group(1), depth + 1)
        text = text[match.end():]
        continue
      match = re.search("^\[-(.*?)-\]", text)
      if match:
        output += UnescapeText(match.group(1), depth + 1)
        text = text[match.end():]
        continue
      match = re.search("^\[#(.*?)#\]", text)
      if match:
        output += UnescapeText(match.group(1), depth + 1)
        text = text[match.end():]
        continue
      match = re.search("^\[\^(.*?)\^\]", text)
      if match:
        output += UnescapeText(match.group(1), depth + 1)
        text = text[match.end():]
        continue
      match = re.search("^\[,(.*?),\]", text)
      if match:
        output += UnescapeText(match.group(1), depth + 1)
        text = text[match.end():]
        continue
      match = re.search("^\[:(.*?):\]", text)
      if match:
        output += UnescapeText(match.group(1), depth + 1)
        text = text[match.end():]
        continue
      match = re.search("^\[\.(.*?)\.\]", text)
      if match:
        output += UnescapeText(match.group(1), depth + 1)
        text = text[match.end():]
        continue
      match = re.search("^\[{(#?[A-Za-z0-9]+):(.*?)}\]", text)
      if match:
        output += UnescapeText(match.group(1), depth + 1)
        text = text[match.end():]
        continue
      match = re.search("^\[\(([^:]+):(.*?)\)\]", text)
      if match:
        output += UnescapeText(match.group(1), depth + 1)
        text = text[match.end():]
        continue
      match = re.search("^\[\[(.*?)\]\]", text)
      if match:
        content = match.group(1)
        submatch = re.fullmatch(r"(.*?)\|(.*)", content)
        if submatch:
          face = submatch.group(1).strip()
        else:
          face = content.strip()
        output += UnescapeText(face, depth + 1)
        text = text[match.end():]
        continue
      output += "["
      text = text[1:]
    else:
      output += text
      break
  return output


def MakeDescription(sections):
  desc_texts = []
  for section in sections:
    elem_type = section["type"]
    lines = section["lines"][:]
    if elem_type == "h":
      for line in lines:
        match = re.search("^(\*+) +(.*)$", line)
        level = min(len(match.group(1)), 3)
        text = match.group(2).strip()
        if text:
          desc_texts.append(text)
    if elem_type == "p":
      column_match = re.search(r"^\[!(.*?)!\](.*)$", lines[0])
      if column_match:
        caption = column_match.group(1)
        lines[0] = column_match.group(2).strip()
        if caption.startswith("~"):
          caption = caption[1:]
        text = UnescapeText(caption, 1)
        if text:
          desc_texts.append(text)
        for line in lines:
          text = UnescapeText(text, 1)
          if text:
            desc_texts.append(text)
      else:
        match = re.search(r"^(>+) +(.*)$", lines[0])
        if match:
          lines[0] = match.group(2).strip()
        for line in lines:
          text = UnescapeText(line, 1)
          if text:
            desc_texts.append(text)
    if elem_type == "pre":
      for line in lines:
        text = UnescapeText(text, 1)
        if text:
          desc_texts.append(text)
  joined = " ".join(desc_texts)
  joined = re.sub(r"\s+", " ", joined).strip()
  joined = CutTextByWidth(joined, MAX_DESCRIPTION_WIDTH)
  return joined


def PrintArticle(config, articles, index, article, sections, output_file):
  def P(*args, end="\n"):
    esc_args = []
    for arg in args[1:]:
      if isinstance(arg, str):
        arg = esc(arg)
      esc_args.append(arg)
    print(args[0].format(*esc_args), end=end, file=output_file)
  site_url = config["site_url"]
  page_url = re.sub(r"/[^/]+$", "/", site_url)
  page_url += urllib.parse.quote(GetOutputFilename(article["name"]))
  title = NormalizeMetaText(article.get("title") or "")
  date = NormalizeMetaText(article.get("date") or "")
  misc = NormalizeMetaText(article.get("misc") or "")
  misc = re.sub(r" *, *", ", ", misc).strip()
  site_title = config["title"]
  site_subtitle = config.get("subtitle")
  if title:
    page_title = site_title + ": " + title
    site_title_subclass = "site_title_area_weak"
  else:
    page_title = site_title
    site_title_subclass = "site_title_area_strong"
  extra_site_title = ""
  if site_subtitle:
    extra_site_title = '\n<div class="subtitle">{}</div>'.format(esc(site_subtitle))
  desc = NormalizeMetaText(article.get("desc") or "")
  if not desc:
    desc = MakeDescription(sections)
  extra_head_lines = []
  if title:
    extra_head_lines.append('<meta name="x-bbb-title" content="{}"/>'.format(title))
  if date:
    extra_head_lines.append('<meta name="x-bbb-date" content="{}"/>'.format(date))
  if misc:
    extra_head_lines.append('<meta name="x-bbb-misc" content="{}"/>'.format(misc))
  for expr in config.get("extra_meta") or []:
    fields = expr.split("|", 1)
    if len(fields) != 2: continue
    meta_html = '<meta name="{}" content="{}"/>'.format(
      esc(fields[0].strip()), esc(fields[1].strip()))
    extra_head_lines.append(meta_html)
  if desc:
    meta_html = '<meta name="description" content="{}"/>'.format(esc(desc))
    extra_head_lines.append(meta_html)
  meta_html = '<meta property="og:url" content="{}"/>'.format(esc(page_url))
  extra_head_lines.append(meta_html)
  meta_html = '<meta property="og:title" content="{}"/>'.format(esc(title or site_title))
  extra_head_lines.append(meta_html)
  meta_html = '<meta property="og:site_name" content="{}"/>'.format(esc(site_title))
  extra_head_lines.append(meta_html)
  og_type = "article" if title else "website"
  meta_html = '<meta property="og:type" content="{}"/>'.format(esc(og_type))
  extra_head_lines.append(meta_html)
  if desc:
    meta_html = '<meta property="og:description" content="{}"/>'.format(esc(desc))
    extra_head_lines.append(meta_html)
  locale = config["language"] + "_ZZ"
  meta_html = '<meta property="og:locale" content="{}"/>'.format(esc(locale))
  extra_head_lines.append(meta_html)
  image = article.get("image")
  if image:
    meta_html = '<meta property="og:image" content="{}"/>'.format(esc(image))
    extra_head_lines.append(meta_html)
  if "extra_head_lines" in config:
    extra_head_lines.extend(config["extra_head_lines"])
  extra_body_header_lines = []
  if "extra_body_header_lines" in config:
    extra_body_header_lines.append("")
    extra_body_header_lines.extend(config["extra_body_header_lines"])
  extra_body_footer_lines = []
  if "extra_body_footer_lines" in config:
    extra_body_footer_lines.extend(config["extra_body_footer_lines"])
    extra_body_footer_lines.append("")
  main_header = MAIN_HEADER_TEXT.format(
    lang=esc(config["language"]),
    extra_head_lines="\n".join(extra_head_lines),
    style_file=esc(os.path.basename(config["style_file"])),
    script_file=esc(os.path.basename(config["script_file"])),
    page_title=esc(page_title),
    site_title=esc(config["title"]),
    site_title_subclass=esc(site_title_subclass),
    extra_site_title=extra_site_title,
    site_url=esc(site_url),
    extra_body_header_lines="\n".join(extra_body_header_lines))
  print(main_header.strip(), file=output_file)
  P('<article class="main">')
  id_count_index = collections.defaultdict(int)
  column_count = 0
  if title or date:
    P('<div class="page_title_area">')
    if title:
      P('<h2 class="article_title"><a href="{}">{}</a></h2>', page_url, title)
    if date:
      P('<div class="article_date">{}</div>', date)
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
          head_id = head_id + "_{:d}".format(id_count)
        id_count_index[head_id] = id_count
        P('<{} id="{}">', elem, head_id, end="")
        P('{}', text, end="")
        P('</' + elem + '>')
    if elem_type == "ul":
      tag_stack = []
      for line in lines:
        match = re.search("^([-+]+) +(.*)$", line)
        level = min(len(match.group(1)), 3)
        tag = "ol" if line.startswith("+") else "ul"
        text = match.group(2)
        while level < len(tag_stack):
          last_tag = tag_stack.pop()
          P('</' + last_tag + '>')
        while level > len(tag_stack):
          P('<' + tag + ' class="ul{:d}">', len(tag_stack) + 1)
          tag_stack.append(tag)
        P('<li class="li{:d}">', level, end="")
        PrintText(P, index, text.strip(), 1)
        P('</li>')
      while tag_stack:
        last_tag = tag_stack.pop()
        P('</' + last_tag + '>')
    if elem_type == "table":
      P('<table class="rows{}">', len(lines))
      for line in lines:
        line = re.sub(r"^\|", "", line)
        line = re.sub(r"\[\[([^\]]+)\|([^\]]+)\]\]", r"[[\1{{_VERT_}}\2]]", line)
        fields = line.split("|")
        P('<tr class="cols{}">', len(fields))
        for field in fields:
          field = re.sub(r"{{_VERT_}}", "|", field)
          spread = False
          match = re.search(r"^<=>(.*)", field)
          if match:
            field = match.group(1)
            spread = True
          colspan = 1
          match = re.search(r"^<(\d+)>(.*)", field)
          if match:
            field = match.group(2)
            colspan = max(1, int(match.group(1)))
          rowspan = 1
          match = re.search(r"^{(\d+)}(.*)", field)
          if match:
            field = match.group(2)
            rowspan = max(1, int(match.group(1)))
          class_name = "str"
          match = re.search(r"^#(.*)", field)
          if match:
            field = match.group(1)
            class_name = "num"
          match = re.search(r"^\^(.*)", field)
          if match:
            field = match.group(1)
            class_name += " head"
          if spread:
            class_name += " spread"
          P('<td colspan="{}" rowspan="{}" class="{}">', colspan, rowspan, class_name, end="")
          PrintText(P, index, field.strip(), 1)
          P('</td>', end="")
        P('</tr>')
      P('</table>')
    if elem_type == "p":
      column_match = re.search(r"^\[!(.*?)!\](.*)$", lines[0])
      if column_match:
        column_count += 1
        caption = column_match.group(1)
        lines[0] = column_match.group(2).strip()
        column_class = "column_overt"
        if caption.startswith("~"):
          column_class = "column_covert"
          caption = caption[1:]
        caption = caption.strip()
        P('<div class="column_trigger_area">')
        P('<span id="column_trigger{}" class="column_trigger {}_trigger"'
          ' onclick="open_column(this);" data-column-id="column{:d}">☞ {}</span>',
          column_count, column_class, column_count, caption or "Column")
        P('</div>')
        P('<section id="column{}" class="column {}">', column_count, column_class)
        P('<div class="column_close" onclick="close_column(this);">×</div>', caption)
        if caption:
          P('<div class="column_caption">{}</div>', caption)
        for line in lines:
          if not line: continue
          P('<div class="column_line">', end="")
          PrintText(P, index, line.strip(), 1)
          P('</div>')
        P('</section>')
      else:
        level = 0
        match = re.search(r"^(>+) +(.*)$", lines[0])
        if match:
          level = min(4, len(match.group(1)))
          lines[0] = match.group(2).strip()
        P('<p class="lv{:d}">', level, end="")
        for i, line in enumerate(lines):
          PrintText(P, index, line.strip(), 1)
          if i < len(lines) - 1:
            P('<br/>')
        P('</p>')
    if elem_type == "pre":
      P('<pre>', end="")
      for line in lines:
        P('{}', line)
      P('</pre>')
    if elem_type == "hr":
      level = len(lines[0]) - 2
      P('<hr class="hr{}"/>', level)
    if elem_type == "meta":
      match = re.search("^@([-_a-z]+)(.*)$", lines[0])
      name = match.group(1)
      params = match.group(2).strip()
      if name == "image":
        PrintImage(P, params)
      elif name == "video":
        PrintVideo(P, params)
      elif name == "youtube":
        PrintYoutube(P, params)
      elif name == "maps":
        PrintMaps(P, params)
      elif name == "site-tags":
        PrintSiteTags(P, articles, params)
      elif name == "page-toc":
        PrintPageToc(P, sections, params)
      elif name == "site-toc":
        PrintSiteToc(P, articles, params)
      elif name == "comment-history":
        PrintCommentHistory(config, P, params)
      elif name == "search":
        PrintSearch(config, P, params)
      elif name not in ["title", "date", "tags", "misc", "desc"]:
        logger.warning("unknown meta directive: {}".format(name))
  P('</article>')
  PrintShareButtons(config, output_file, P, article)
  PrintTags(config, P, article)
  PrintStepLinks(config, P, articles, article)
  PrintComments(config, P, article)
  main_footer = MAIN_FOOTER_TEXT.format(
    extra_body_footer_lines="\n".join(extra_body_footer_lines))
  print(main_footer.strip(), file=output_file)


def PrintText(P, index, text, depth):
  if depth > 10:
    P('{}', text, end="")
    return
  while True:
    idx = text.find("[")
    if idx >= 0:
      if idx > 0:
        P('{}', text[:idx], end="")
        text = text[idx:]
      match = re.search(r"^\[\\n\]", text)
      if match:
        P('<br/>')
        text = text[match.end():]
        continue
      match = re.search(r"^\[\\t\]", text)
      if match:
        P('&#x2003;&#x2003;')
        text = text[match.end():]
        continue
      match = re.search("^\[\|\|(.*?)\|\|\]", text)
      if match:
        P('{}', match.group(1), end="")
        text = text[match.end():]
        continue
      match = re.search("^\[\*(.*?)\*\]", text)
      if match:
        P('<b>', end="")
        PrintText(P, index, match.group(1), depth + 1)
        P('</b>', end="")
        text = text[match.end():]
        continue
      match = re.search("^\[/(.*?)/\]", text)
      if match:
        P('<i>', end="")
        PrintText(P, index, match.group(1), depth + 1)
        P('</i>', end="")
        text = text[match.end():]
        continue
      match = re.search("^\[_(.*?)_\]", text)
      if match:
        P('<u>', end="")
        PrintText(P, index, match.group(1), depth + 1)
        P('</u>', end="")
        text = text[match.end():]
        continue
      match = re.search("^\[-(.*?)-\]", text)
      if match:
        P('<s>', end="")
        PrintText(P, index, match.group(1), depth + 1)
        P('</s>', end="")
        text = text[match.end():]
        continue
      match = re.search("^\[#(.*?)#\]", text)
      if match:
        P('<kbd>', end="")
        PrintText(P, index, match.group(1), depth + 1)
        P('</kbd>', end="")
        text = text[match.end():]
        continue
      match = re.search("^\[\^(.*?)\^\]", text)
      if match:
        P('<sup>', end="")
        PrintText(P, index, match.group(1), depth + 1)
        P('</sup>', end="")
        text = text[match.end():]
        continue
      match = re.search("^\[,(.*?),\]", text)
      if match:
        P('<sub>', end="")
        PrintText(P, index, match.group(1), depth + 1)
        P('</sub>', end="")
        text = text[match.end():]
        continue
      match = re.search("^\[:(.*?):\]", text)
      if match:
        P('<big>', end="")
        PrintText(P, index, match.group(1), depth + 1)
        P('</big>', end="")
        text = text[match.end():]
        continue
      match = re.search("^\[\.(.*?)\.\]", text)
      if match:
        P('<small>', end="")
        PrintText(P, index, match.group(1), depth + 1)
        P('</small>', end="")
        text = text[match.end():]
        continue
      match = re.search("^\[{(#?[A-Za-z0-9]+):(.*?)}\]", text)
      if match:
        P('<span style="color:{};" class="colored">', match.group(1), end="")
        PrintText(P, index, match.group(2), depth + 1)
        P('</span>', end="")
        text = text[match.end():]
        continue
      match = re.search("^\[\(([^:]+):(.*?)\)\]", text)
      if match:
        P('<ruby><rb>', end="")
        PrintText(P, index, match.group(1), depth + 1)
        P('</rb><rt>{}</rt></ruby>', match.group(2), end="")
        text = text[match.end():]
        continue
      match = re.search("^\[\[(.*?)\]\]", text)
      if match:
        content = match.group(1)
        submatch = re.fullmatch(r"(.*?)\|(.*)", content)
        if submatch:
          face = submatch.group(1).strip()
          dest = submatch.group(2).strip()
        else:
          face = content.strip()
          dest = content.strip()
        dest_url = ""
        link_class = "internal"
        if re.search(r"^https?://", dest):
          dest_url = dest
          link_class = "external"
        elif dest.startswith("enwiki:"):
          dest = dest[7:].strip()
          if not dest and face:
            dest = face
          dest_url = "https://en.wikipedia.org/wiki/" + urllib.parse.quote(dest)
          link_class = "external"
        elif dest.startswith("jawiki:"):
          dest = dest[7:].strip()
          if not dest and face:
            dest = face
          dest_url = "https://ja.wikipedia.org/wiki/" + urllib.parse.quote(dest)
          link_class = "external"
        elif dest.startswith("google:"):
          dest = dest[7:].strip()
          if not dest and face:
            dest = face
          dest_url = "https://google.com/search?q=" + urllib.parse.quote(dest)
          link_class = "external"
        else:
          submatch = re.search(r"(^[^#]*)#(.+)$", dest)
          if submatch:
            dest_title = submatch.group(1)
            dest_fragment = submatch.group(2)
          else:
            dest_title = dest
            dest_fragment = ""
          if dest_title:
            dest_article = index.get(dest_title.lower())
            if dest_article:
              dest_url = "./" + urllib.parse.quote(GetOutputFilename(dest_article["name"]))
              if dest_fragment:
                dest_url = dest_url + "#" + EscapeHeaderId(dest_fragment)
          elif dest_fragment:
            dest_url = "#" + EscapeHeaderId(dest_fragment)
        if not dest_url:
          logger.warning("invalid hyperlink: {}: {}".format(face, dest))
          link_class = "dead"
        if re.search(r"^https?://.{30,}", face):
          link_class += " long_expr"
        P('<a href="{}" class="{}">', dest_url, link_class, end="")
        PrintText(P, index, face, depth + 1)
        P('</a>', end="")
        text = text[match.end():]
        continue
      P('[', end="")
      text = text[1:]
    else:
      P('{}', text, end="")
      break


def ParseMetaParams(params):
  attrs = {}
  while True:
    match = re.search(r"^(.*?)\[([a-z]+?)=(.*?)\](.*)$", params)
    if match:
      attr_name = match.group(2).strip()
      attr_value = match.group(3).strip()
      if attr_name:
        attrs[attr_name] = attr_value
      params = (match.group(1) + " " + match.group(4)).strip()
      continue
    match = re.search(r"^(.*?)\[([a-z]+?)\](.*)$", params)
    if match:
      attr_name = match.group(2).strip()
      if attr_name:
        attrs[attr_name] = True
      params = (match.group(1) + " " + match.group(3)).strip()
      continue
    break
  attrs[""] = params.strip()
  return attrs


def ParseMisc(misc):
  tags = []
  for tag in misc.split(","):
    tag = re.sub(r"\s+", " ", tag).strip()
    if not tag or tag in tags: continue
    tags.append(tag)
  return tags


def PrintImage(P, params):
  columns = params.split("|")
  is_frill = re.search(r"\W\[frill(=\w*)?\](\W|$)", params)
  if len(columns) == 1:
    attrs = ParseMetaParams(columns[0])
    float_dir = attrs.get("float")
    if float_dir in ["left", "right"]:
      attrs = ParseMetaParams(columns[0])
      url = attrs[""]
      caption = attrs.get("caption")
      width = attrs.get("width")
      css_classes = ["image_float", "image_float_" + float_dir]
      if is_frill:
        css_classes.append("image_frill")
      styles = []
      if width:
        num_width = re.sub(r"[^0-9]", "", width)
        if num_width:
          styles.append("max-width: {}%".format(num_width))
      P('<span class="{}" style="{}">', " ".join(css_classes), ";".join(styles))
      if caption:
        P('<span class="image_caption image_caption2">{}</span>', caption, end="")
      P('<a href="{}">', url, end="")
      P('<img src="{}" loading="lazy" class="float_image"/>', url, end="")
      P('</a>', end="")
      P('</span>')
      return
  css_classes = ["image_area"]
  if is_frill:
    css_classes.append("image_frill")
  P('<div class="{}">', " ".join(css_classes))
  for column in columns:
    attrs = ParseMetaParams(column)
    url = attrs[""]
    caption = attrs.get("caption")
    width = attrs.get("width")
    styles = []
    if width:
      num_width = re.sub(r"[^0-9]", "", width)
      if num_width:
        styles.append("max-width: {}%".format(num_width))
    P('<span class="image_cell">', end="")
    if caption:
      P('<span class="image_caption image_caption{}">{}</span>',
        len(columns), caption, end="")
    P('<a href="{}">', url, end="")
    P('<img src="{}" loading="lazy" class="emb_image emb_image{}" style="{}"/>',
      url, len(columns), ";".join(styles), end="")
    P('</a>', end="")
    P('</span>')
  P('</div>')


def PrintVideo(P, params):
  columns = params.split("|")
  is_frill = re.search(r"\W\[frill(=\w*)?\](\W|$)", params)
  if len(columns) == 1:
    attrs = ParseMetaParams(columns[0])
    float_dir = attrs.get("float")
    if float_dir in ["left", "right"]:
      attrs = ParseMetaParams(columns[0])
      url = attrs[""]
      caption = attrs.get("caption")
      width = attrs.get("width")
      css_classes = ["video_float", "video_float_" + float_dir]
      if is_frill:
        css_classes.append("video_frill")
      styles = []
      if width:
        num_width = re.sub(r"[^0-9]", "", width)
        if num_width:
          styles.append("max-width: {}%".format(num_width))
      P('<span class="{}" style="{}">', " ".join(css_classes), ";".join(styles))
      if caption:
        P('<span class="video_caption image_caption2">{}</span>', caption, end="")
      P('<video src="{}" controls="controls" preload="metadata" class="float_video"/>',
        url, len(columns), end="")
      P('</span>')
      return
  css_classes = ["video_area"]
  if is_frill:
    css_classes.append("video_frill")
  P('<div class="{}">', " ".join(css_classes))
  for column in columns:
    attrs = ParseMetaParams(column)
    url = attrs[""]
    caption = attrs.get("caption")
    width = attrs.get("width")
    styles = []
    if width:
      num_width = re.sub(r"[^0-9]", "", width)
      if num_width:
        styles.append("max-width: {}%".format(num_width))
    P('<span class="video_cell">', end="")
    if caption:
      P('<span class="video_caption video_caption{}">{}</span>',
        len(columns), caption, end="")
    P('<video src="{}" controls="controls" preload="metadata"'
      ' class="emb_video emb_video{}" style="{}"/>',
      url, len(columns), ";".join(styles), end="")
    P('</span>')
  P('</div>')


def PrintYoutube(P, params):
  columns = params.split("|")
  if len(columns) == 1:
    attrs = ParseMetaParams(columns[0])
    float_dir = attrs.get("float")
    if float_dir in ["left", "right"]:
      attrs = ParseMetaParams(columns[0])
      url = attrs[""]
      caption = attrs.get("caption")
      width = attrs.get("width")
      styles = []
      if width:
        num_width = re.sub(r"[^0-9]", "", width)
        if num_width:
          styles.append("max-width: {}%".format(num_width))
      P('<span class="youtube_float youtube_float_{}" style="{}">', float_dir, ";".join(styles))
      if caption:
        P('<span class="youtube_caption youtube_caption2">{}</span>', caption, end="")
      video_id = ""
      match = re.search(r"[?&]v=([-_a-zA-Z0-9]+)([&#]|$)", url)
      if match:
        video_id = match.group(1)
      else:
        video_id = re.sub(r"^https?://[a-z0-9\.]+/", "", url)
        video_id = re.sub(r"[^_a-zA-Z0-9]", "", video_id)[:16]
      url = "https://www.youtube-nocookie.com/embed/" + video_id
      P('<iframe src="{}" loading="lazy" frameborder="0" class="youtube{}"></iframe>',
        url, len(columns), end="")
      P('</span>')
      return
  P('<div class="youtube_area">')
  for column in columns:
    attrs = ParseMetaParams(column)
    url = attrs[""]
    caption = attrs.get("caption")
    width = attrs.get("width")
    styles = []
    if width:
      num_width = re.sub(r"[^0-9]", "", width)
      if num_width:
        styles.append("width: {}%".format(num_width))
    P('<span class="youtube_cell">', end="")
    if caption:
      P('<span class="youtube_caption youtube_caption{}">{}</span>',
        len(columns), caption, end="")
    video_id = ""
    match = re.search(r"[?&]v=([-_a-zA-Z0-9]+)([&#]|$)", url)
    if match:
      video_id = match.group(1)
    else:
      video_id = re.sub(r"^https?://[a-z0-9\.]+/", "", url)
      video_id = re.sub(r"[^_a-zA-Z0-9]", "", video_id)[:16]
    url = "https://www.youtube-nocookie.com/embed/" + video_id
    P('<iframe src="{}" loading="lazy" frameborder="0" class="youtube{}" style="{}"></iframe>',
      url, len(columns), ";".join(styles), end="")
    P('</span>')
  P('</div>')


def PrintMaps(P, params):
  columns = params.split("|")
  if len(columns) == 1:
    attrs = ParseMetaParams(columns[0])
    float_dir = attrs.get("float")
    if float_dir in ["left", "right"]:
      attrs = ParseMetaParams(columns[0])
      query = attrs[""]
      zoom = attrs.get("zoom")
      caption = attrs.get("caption")
      width = attrs.get("width")
      styles = []
      if width:
        num_width = re.sub(r"[^0-9]", "", width)
        if num_width:
          styles.append("max-width: {}%".format(num_width))
      P('<span class="maps_float maps_float_{}" style="{}">', float_dir, ";".join(styles))
      if caption:
        P('<span class="maps_caption maps_caption2">{}</span>', caption, end="")
      url = "https://maps.google.co.jp/maps?q=" + urllib.parse.quote(query)
      if zoom:
        url += "&z=" + zoom
      url += "&output=embed"
      P('<iframe src="{}" loading="lazy" frameborder="0" class="maps{}" style="{}"></iframe>',
        url, len(columns), ";".join(styles), end="")
      P('</span>')
      return
  P('<div class="maps_area">')
  for column in columns:
    attrs = ParseMetaParams(column)
    query = attrs[""]
    zoom = attrs.get("zoom")
    caption = attrs.get("caption")
    width = attrs.get("width")
    styles = []
    if width:
      num_width = re.sub(r"[^0-9]", "", width)
      if num_width:
        styles.append("width: {}%".format(num_width))
    P('<span class="maps_cell">', end="")
    if caption:
      P('<span class="maps_caption maps_caption{}">{}</span>',
        len(columns), caption, end="")
    url = "https://maps.google.co.jp/maps?q=" + urllib.parse.quote(query)
    if zoom:
      url += "&z=" + zoom
    url += "&output=embed"
    P('<iframe src="{}" loading="lazy" frameborder="0" class="maps{}" style="{}"></iframe>',
      url, len(columns), ";".join(styles), end="")
    P('</span>')
  P('</div>')


def PrintSiteTags(P, articles, params):
  tag_index = collections.defaultdict(list)
  for article in articles:
    tags = ParseMisc(article.get("tags") or "")
    for tag in tags:
      tag_index[tag].append(article)
  sorted_tags = sorted(tag_index.items(), key=lambda x: (-len(x[1]), x[0]))
  P('<dl class="site_tags_area">')
  for tag, tag_articles in sorted_tags:
    P('<dt class="site_tags_name">{} <span class="site_tags_count">({:d})</span></dt>',
      tag, len(tag_articles))
    P('<dd class="site_tags_resources">')
    for i, article in enumerate(tag_articles):
      if i > 0:
        P(', ', end="")
      name = article["name"]
      title = article.get("title") or article["stem"]
      url = "./" + urllib.parse.quote(GetOutputFilename(name))
      P('<a href="{}" class="site_tags_link">{}</a>', url, title)
    P('</dd>')
  P('</dl>')


def PrintPageToc(P, sections, params):
  P('<ul class="page_toc_area">')
  id_count_index = collections.defaultdict(int)
  for section in sections:
    elem_type = section["type"]
    lines = section["lines"]
    if elem_type != 'h': continue
    for line in lines:
      match = re.search("^(\*+) +(.*)$", line)
      level = min(len(match.group(1)), 3)
      text = match.group(2)
      head_id = EscapeHeaderId(text)
      id_count = id_count_index[head_id]
      id_count += 1
      if id_count > 1:
        head_id = head_id + "_{:d}".format(id_count)
      id_count_index[head_id] = id_count
      P('<li class="pagetoc{}">', level, end="")
      P('<a href="#{}">{}</a>', head_id, text, end="")
      P('</li>')
  P('</ul>')


def PrintSiteToc(P, articles, params):
  P('<div class="site_toc_area">')
  attrs = ParseMetaParams(params)
  order = attrs.get("order")
  reverse = ToBool(attrs.get("reverse"))
  max_num = int(attrs.get("max") or 0)
  articles = [x for x in articles if "notoc" not in ParseMisc(x.get("misc") or "")]
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
    name = article["name"]
    url = "./" + urllib.parse.quote(GetOutputFilename(name))
    title = article.get("title")
    if not title:
      title = article["stem"]
    date = article.get("date")
    P('<li class="site_toc_item">', end="")
    P('<a href="{}">{}</a>', url, title, end="")
    if date:
      P(' <span class="attrdate">({})</span>', date, end="")
    P('</li>')
  P('</ul>')
  P('</div>')


def PrintCommentHistory(config, P, params):
  attrs = ParseMetaParams(params)
  max_num = int(attrs.get("max") or 0)
  perpage = int(attrs.get("perpage") or 0)
  comment_url = config.get("comment_url") or ""
  if not comment_url:
    P('<div>(@comment-history: comment_url is not set)</div>')
    return
  P('<div class="comment_history_area" data-comment-url="{}"'
    ' data-comment-max="{}" data-comment-perpage="{}"></div>',
    comment_url, max_num, perpage)


def PrintSearch(config, P, params):
  attrs = ParseMetaParams(params)
  max_num = int(attrs.get("max") or 0)
  perpage = int(attrs.get("perpage") or 0)
  search_url = config.get("search_url") or ""
  if not search_url:
    P('<div>(@search: search_url is not set)</div>')
    return
  P('<div class="search_area" data-search-url="{}"'
    ' data-search-max="{}" data-search-perpage="{}">',
    search_url, max_num, perpage)
  P('<form class="search_form" onsubmit="search_fulltext(this); return false;">')
  P('<div class="search_line">')
  P('<span class="search_control">')
  P('<input type="text" class="search_query" value=""/>')
  P('<select class="search_order">')
  P('<option value="score">order: score</option>')
  P('<option value="name">name asc</option>')
  P('<option value="name_r">name desc</option>')
  P('<option value="title">title asc</option>')
  P('<option value="title_r">title desc</option>')
  P('<option value="date">date asc</option>')
  P('<option value="date_r">date desc</option>')
  P('</select>')
  P('<input type="button" class="search_search" value="search" onclick="search_fulltext(this);"/>')
  P('</span>')
  P('</div>')
  P('</form>')
  P('<div class="search_result"></div>')
  P('</div>')


def PrintShareButtons(config, output_file, P, article):
  misc = ParseMisc(article.get("misc") or "")
  if "noshare" in misc: return
  button_names = config.get("share_button")
  if not button_names: return
  P('<div class="share_button_area">')
  P('<span class="share_button_container"><table><tr>')
  dest_url = re.sub(r"/[^/]+$", "/", config["site_url"])
  dest_url += urllib.parse.quote(GetOutputFilename(article["name"]))
  lang = config["language"]
  for button_name in button_names:
    P('<td>')
    if button_name == "twitter":
      button = TWITTER_BUTTON_TEXT.format()
      print(button.strip(), file=output_file)
    if button_name == "line":
      button = LINE_BUTTON_TEXT.format(
        url=dest_url,
        lang=esc(lang))
      print(button.strip(), file=output_file)
    if button_name == "facebook":
      locale = "en_US"
      if lang == "ja":
        locale = "ja_JP"
      button = FACEBOOK_BUTTON_TEXT.format(
        url=dest_url,
        locale=esc(locale))
      print(button.strip(), file=output_file)
    if button_name == "hatena":
      button = HATENA_BUTTON_TEXT.format(
        lang=esc(lang))
      print(button.strip(), file=output_file)
    P('</td>')
  P('</tr></table></span>')
  P('</div>')


def PrintTags(config, P, article):
  tags = ParseMisc(article.get("tags") or "")
  if not tags: return
  P('<div class="tags_area">')
  P('<div class="tags_list">')
  for tag in tags:
    P('<span onclick="search_tags(this);" class="tag">{}</span>', tag)
  P('</div>')
  stem = article["stem"]
  P('<div id="tags_result" data-resource="{}"></div>', stem)
  P('</div>')


def PrintStepLinks(config, P, articles, article):
  misc = ParseMisc(article.get("misc") or "")
  if "notoc" in misc: return
  step_order = config.get("step_order")
  name = article["name"]
  title = article.get("title") or ""
  date = article.get("date") or ""
  if step_order == "title":
    if not title: return
    self_expr = title + "\0" + name
  elif step_order == "date":
    if not date: return
    self_expr = date + "\0" + name
  elif step_order == "filename":
    self_expr = name
  else:
    return
  prev_article = None
  prev_expr = None
  next_article = None
  next_expr = None
  for sibling in articles:
    if sibling == article: continue
    sibl_misc = ParseMisc(sibling.get("misc") or "")
    if "notoc" in sibl_misc: continue
    sibl_name = sibling["name"]
    sibl_title = sibling.get("title") or ""
    sibl_date = sibling.get("date") or ""
    if step_order == "title":
      if not sibl_title: continue
      sibl_expr = sibl_title + "\0" + sibl_name
    elif step_order == "date":
      if not sibl_date: continue
      sibl_expr = sibl_date + "\0" + sibl_name
    elif step_order == "filename":
      sibl_expr = sibl_name
    else:
      continue
    if sibl_expr < self_expr and (not prev_expr or sibl_expr > prev_expr):
      prev_article = sibling
      prev_expr = sibl_expr
    if sibl_expr > self_expr and (not next_expr or sibl_expr < next_expr):
      next_article = sibling
      next_expr = sibl_expr
  P('<div class="step_link_area">')
  if prev_article:
    prev_url = "./" + urllib.parse.quote(GetOutputFilename(prev_article["name"]))
    prev_title = prev_article.get("title")
    if not prev_title:
      prev_title = prev_article["stem"]
    prev_title = CutTextByWidth(prev_title, 20)
    if len(prev_title) > 24:
      prev_title = prev_title[:24] + "…"
    P('<a href="{}" class="step_button">←', prev_url, end="")
    if prev_title:
      P('<br/><span class="step_title">{}</span>', prev_title, end="")
    P('</a>')
  if next_article:
    next_url = "./" + urllib.parse.quote(GetOutputFilename(next_article["name"]))
    next_title = next_article.get("title")
    if not next_title:
      next_title = next_article["stem"]
    next_title = CutTextByWidth(next_title or "", 20)
    P('<a href="{}" class="step_button">→', next_url, end="")
    if next_title:
      P('<br/><span class="step_title">{}</span>', next_title, end="")
    P('</a>')
  P('</div>')


def PrintComments(config, P, article):
  misc = ParseMisc(article.get("misc") or "")
  if "nocomment" in misc: return
  comment_url = config.get("comment_url") or ""
  if not comment_url: return
  stem = article["stem"]
  P('<div class="comment_area" id="comment_area" data-comment-url="{}" data-resource="{}">',
    comment_url, stem)
  P('<span id="comment_banner" onclick="render_comments();">comments</span>')
  P('<div id="comment_list">----</div>')
  P('<form id="comment_form" onsubmit="return false;">')
  P('<table>')
  P('<tr>')
  P('<td class="comment_form_label">name:</td>')
  P('<td class="comment_form_data">')
  P('<input type="text" value="" id="comment_author" size="20" autocomplete="off"/>')
  P('</td>')
  P('</tr>')
  P('<tr>')
  P('<td class="comment_form_label">text:</td>')
  P('<td class="comment_form_data">')
  P('<textarea id="comment_text" cols="30" rows="8" autocomplete="off"></textarea>')
  P('</td>')
  P('</tr>')
  P('<tr>')
  P('<td class="comment_form_label"></td>')
  P('<td>')
  P('<button id="comment_post" onclick="post_comment();">post</button>')
  P('<span id="comment_message"></span>')
  P('</td>')
  P('</tr>')
  P('</table>')
  P('</form>')
  P('</div>')


def MakeTocFile(config, articles):
  output_dir = config["output_dir"]
  toc_path = os.path.join(output_dir, "__toc__.tsv")
  with open(toc_path, "w") as output_file:
    for article in articles:
      stem = article["stem"]
      short_title = (article.get("title") or "")
      if len(short_title) > 64:
        short_title = short_title[:64] + "..."
      date = (article.get("date") or "")[:32]
      tags = ParseMisc(article.get("tags") or "")
      print("{}\t{}\t{}\t{}".format(
        stem, short_title, date, ", ".join(tags)),
            file=output_file)


if __name__ == "__main__":
  sys.exit(main(sys.argv[1:]))


# END OF FILE
