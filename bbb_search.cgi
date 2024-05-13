#! /usr/bin/python3
# -*- coding: utf-8 -*-
#--------------------------------------------------------------------------------------------------
# Search articles
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


import cgi
import html
import os
import re
import sys
import urllib
import urllib.parse


HTML_DIR = "."
MAX_QUERIES = 10
SNIPPET_WIDTH = 64
NUM_SNIPPETS_PER_QUERY = 2
CHECK_REFERRER = True


def main():
  script_filename = os.environ.get("SCRIPT_FILENAME", "")
  script_url = os.environ.get("REQUEST_SCHEME" or "http") + "://"
  script_url += os.environ.get("HTTP_HOST" or "localhost")
  script_url += os.environ.get("REQUEST_URI" or "/bbb_comment.cgi")
  script_url = re.sub(r"\?.*", "", script_url)
  referrer_url = os.environ.get("HTTP_REFERER", "")
  if script_filename:
    resource_dir = os.path.join(os.path.dirname(script_filename), HTML_DIR)
  else:
    resource_dir = HTML_DIR
  resource_dir = os.path.realpath(resource_dir)
  form = cgi.FieldStorage()
  params = {}
  for key in form.keys():
    value = form[key]
    if isinstance(value, list):
      params[key] = value[0].value
    else:
      params[key] = value.value
  if CHECK_REFERRER and referrer_url:
    script_parts = urllib.parse.urlparse(script_url)
    referrer_parts = urllib.parse.urlparse(referrer_url)
    if referrer_parts.netloc != script_parts.netloc:
      PrintError(403, "Forbidden", "bad referrer")
      return
  DoSearch(resource_dir, params)


def PrintError(code, name, message):
  print("Status: {:d} {}".format(code, name))
  print("Content-Type: text/plain")
  print()
  print(message)


def TextToInt(text):
  try:
    return int(text)
  except:
    return 0


def ParseQuery(query):
  query = re.sub(r"\s+", " ", query).strip()
  while True:
    match = re.search(r'^([^"]*)"(.*?)"(.*)$', query)
    if not match: break
    query = match.group(1) + " "
    query += re.sub(r" ", "{{_SPACE_}}", match.group(2).strip())
    query += " " + match.group(3)
  elems = []
  for elem in query.split(" "):
    if len(elems) >= MAX_QUERIES: break
    elem = re.sub(r"{{_SPACE_}}", " ", elem)[:256].strip()
    if elem and elem not in elems:
      rq = re.compile(re.escape(elem), re.IGNORECASE)
      elems.append((elem, rq))
  return elems
  

def ReadXHTML(path):
  meta = {}
  texts = []
  with open(path) as input_file:
    in_article = False
    for line in input_file:
      line = line.strip()
      match = re.search(r'<meta .*name="(.*?)".*content="(.*?)".*/>', line)
      if match:
        meta_name = html.unescape(match.group(1).strip())
        meta_value = html.unescape(match.group(2).strip())
        if meta_name and meta_value:
          meta[meta_name] = meta_value
      if re.search(r'<article([\W]|>)', line):
        in_article = True
        continue
      if re.search(r'</article>', line):
        in_article = False
        continue
      if in_article:
        text = line
        text = re.sub(r"<(br)/>", " ", text)
        text = re.sub(r"</(p|div|td)>", " ", text)
        if re.search('^<h2 .*class="article_title".*>.*</h2>', text): continue
        if re.search('^<div .*class="article_date".*>.*</div>', text): continue
        if re.search('^<li .*class="site_toc_item".*>.*</li>', text): continue
        if re.search('^<dt .*class="site_tags_name".*>.*</dt>', text): continue
        if re.search('^<a .*class="site_tags_link".*>.*</a>', text): continue
        text = re.sub(r"<[^>]*?>", "", text)
        text = html.unescape(text)
        text = re.sub(r"\s+", " ", text).strip()
        if text:
          texts.append(text)
  return (meta, texts)


def SegmentWeight(text, query):
  if re.fullmatch(r"\w.*\w", query):
    if re.search(r"(^|\W)" + re.escape(query) + r"(\W|$)", text, re.IGNORECASE):
      weight = 1.0
    else:
      weight = 0.2
  else:
    weight = 1.0    
  return weight


def ParseMisc(misc):
  tags = []
  for tag in misc.split(","):
    tag = re.sub(r"\s+", " ", tag).strip()
    if not tag or tag in tags: continue
    tags.append(tag)
  return tags


def DoSearch(resource_dir, params):
  p_query = (params.get("query") or "").strip()
  p_order = (params.get("order") or "").strip()
  p_max = TextToInt(params.get("max") or "0")
  queries = ParseQuery(p_query)
  if not queries:
    PrintError(400, "Bad Request", "no query")
    return
  print("Content-Type: text/plain; charset=UTF-8")
  print("")
  docs = []
  for name in os.listdir(resource_dir):
    if not name.endswith(".xhtml"): continue
    path = os.path.join(resource_dir, name)
    try:
      meta, texts = ReadXHTML(path)
    except Exception:
      continue
    if meta.get("generator") != "BikiBikiBob": continue
    stem = re.sub(r"\.xhtml$", "", name)
    title = meta.get("x-bbb-title") or ""
    date = meta.get("x-bbb-date") or ""
    misc = ParseMisc(meta.get("x-bbb-misc") or "")
    if "nosearch" in misc: continue
    hit_queries = set()
    snippets = []
    score = 0.0
    if title:
      for query, reg_query in queries:
        match = reg_query.search(title)
        if match:
          hit_queries.add(query)
          score += 1.0 * SegmentWeight(title, query)
    if date:
      for query, reg_query in queries:
        match = reg_query.search(date)
        if match:
          hit_queries.add(query)
          score += 1.0 * SegmentWeight(date, query)
    base_score = 0.3
    for text_index, text in enumerate(texts):
      for query_index, (query, reg_query) in enumerate(queries):
        match = reg_query.search(text)
        if match:
          hit_queries.add(query)
          span = match.span()
          start_pos = span[0]
          width = float(SNIPPET_WIDTH)
          while start_pos > 0 and width > 0:
            start_pos -= 1
            cp = ord(text[start_pos])
            if cp < 0x0200:
              width -= 1.0
            elif cp < 0x03000:
              width -= 1.5
            else:
              width -= 2.0
          end_pos = span[1]
          width = float(SNIPPET_WIDTH)
          while end_pos < len(text) and width > 0:
            end_pos += 1
            cp = ord(text[end_pos-1])
            if cp < 0x0200:
              width -= 1.0
            elif cp < 0x03000:
              width -= 1.5
            else:
              width -= 2.0
          segment = text[start_pos:end_pos]
          snippet = ""
          if start_pos > 0:
            snippet += "..."
          snippet += segment
          if end_pos < len(text):
            snippet += "..."
          snippets.append((query, snippet, text_index, span[0], span[1]))
          score += base_score * SegmentWeight(text, query)
          next_index = query_index + 1
          if next_index < len(queries):
            next_query, next_reg_query = queries[next_index]
            trailing = text[span[1]:end_pos].strip()
            next_match = next_reg_query.search(trailing)
            if next_match:
              next_weight = 0.5 if next_match.span()[0] == 0 else 0.1
              score += base_score * SegmentWeight(trailing, next_query) * next_weight
      base_score *= 0.98
    all_hit = True
    for query, reg_query in queries:
      if query not in hit_queries:
        all_hit = False
    if not all_hit: continue
    chosen_snippets = []
    query_counts = {}
    covered_end = 0
    for query, text, text_index, pos, end in snippets:
      pos += text_index * 1000000
      end += text_index * 1000000
      if pos < covered_end: continue
      covered_end = max(covered_end, end)
      query_count = (query_counts.get(query) or 0) + 1
      if query_count > NUM_SNIPPETS_PER_QUERY: continue
      query_counts[query] = query_count
      chosen_snippets.append(text)
    doc = {
      "name": stem,
      "title": title,
      "date": date,
      "snippets": chosen_snippets,
      "score": score,
    }
    docs.append(doc)
  if p_order == "name":
    docs = sorted(docs, key=lambda x: x["name"])
  elif p_order == "name_r":
    docs = sorted(docs, key=lambda x: x["name"], reverse=True)
  elif p_order == "title":
    docs = sorted(docs, key=lambda x: (x["title"], x["name"]))
  elif p_order == "title_r":
    docs = sorted(docs, key=lambda x: (x["title"], x["name"]), reverse=True)
  elif p_order == "date":
    docs = sorted(docs, key=lambda x: (x["date"], x["name"]))
  elif p_order == "date_r":
    docs = sorted(docs, key=lambda x: (x["date"], x["name"]), reverse=True)
  else:
    docs = sorted(docs, key=lambda x: (-x["score"], x["name"]))
  for doc in docs:
    fields = []
    fields.append(doc["name"])
    fields.append("{:.3f}".format(doc["score"]))
    fields.append(doc["title"])
    fields.append(doc["date"])
    for snippet in doc["snippets"]:
      fields.append(snippet)
    print("\t".join(fields))


if __name__=="__main__":
  main()


# END OF FILE
