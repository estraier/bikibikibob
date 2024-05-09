#! /usr/bin/python3
# -*- coding: utf-8 -*-
#--------------------------------------------------------------------------------------------------
# Manage comments on articles
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
import datetime
import dateutil.tz
import fcntl
import hashlib
import html
import os
import re
import sys
import time
import unicodedata
import urllib
import urllib.parse


HTML_DIR = "."
COMMENT_DIR = "."
HISTORY_FILE = "__cmthst__.tsv"
NONCE_SALT = "bbb"
MAX_AUTHOR_LEN = 32
MAX_TEXT_LEN = 3000
MAX_COMMENT_FILE_SIZE = 1024 * 1024 * 1
MAX_HISTORY_FILE_SIZE = 1024 * 256
CHECK_REFERRER = True
CHECK_METHOD = False
CHECK_NONCE = True


def main():
  request_method = os.environ.get("REQUEST_METHOD", "GET")
  script_filename = os.environ.get("SCRIPT_FILENAME", "")
  script_url = os.environ.get("REQUEST_SCHEME" or "http") + "://"
  script_url += os.environ.get("HTTP_HOST" or "localhost")
  script_url += os.environ.get("REQUEST_URI" or "/bbb_comment.cgi")
  referrer_url = os.environ.get("HTTP_REFERER", "")
  remote_addr = os.environ.get("REMOTE_ADDR", "")
  if script_filename:
    resource_dir = os.path.join(os.path.dirname(script_filename), HTML_DIR)
    comment_dir = os.path.join(os.path.dirname(script_filename), COMMENT_DIR)
  else:
    resource_dir = HTML_DIR
    comment_dir = COMMENT_DIR
  resource_dir = os.path.realpath(resource_dir)
  form = cgi.FieldStorage()
  params = {}
  for key in form.keys():
    value = form[key]
    if isinstance(value, list):
      params[key] = value[0].value
    else:
      params[key] = value.value
  action = params.get("action") or ""
  if CHECK_REFERRER and referrer_url:
    script_parts = urllib.parse.urlparse(script_url)
    referrer_parts = urllib.parse.urlparse(referrer_url)
    if referrer_parts.netloc != script_parts.netloc:
      PrintError(403, "Forbidden", "bad referrer")
      return
  if action == "list-resources":
    DoListResources(resource_dir, params)
    return
  if action == "list-comments":
    DoListComments(resource_dir, comment_dir, params)
    return
  if action == "count-comments":
    DoCountComments(resource_dir, comment_dir, params)
    return
  if action == "get-nonce":
    DoGetNonce(resource_dir, comment_dir, params)
    return
  if action == "post-comment":
    if CHECK_METHOD and request_method != "POST":
      PrintError(403, "Forbidden", "bad method")
      return
    DoPostComment(resource_dir, comment_dir, params, remote_addr)
    return
  if action == "list-history":
    DoListHistory(comment_dir, params)
    return
  PrintError(400, "Bad Request", "unknown action")
  return


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


def ReadResourceMeta(path):
  is_article = False
  title = ""
  date = ""
  try:
    with open(path) as input_file:
      num_lines = 0
      for line in input_file:
        line = line.strip()
        if re.search(r'<meta .*name="generator".*content="BikiBikiBob".*/>', line):
          is_article = True
          continue
        match = re.search('<meta .*name="x-bbb-title".*content="(.*?)".*/>', line)
        if match:
          title = html.unescape(match.group(1))
        match = re.search('<meta .*name="x-bbb-date".*content="(.*?)".*/>', line)
        if match:
          date = html.unescape(match.group(1))
        num_lines += 1
        if num_lines >= 30 or line == "</head>": break
  except:
    return None
  if not is_article:
    return None
  return (title, date)


def EscapeCommentText(text):
  text = text.replace("\\", "\\\\")
  text = text.replace("\n", "\\n")
  text = re.sub(r"\s", " ", text)
  return text


def GetCurrentDate():
  date = datetime.datetime.fromtimestamp(time.time(), dateutil.tz.tzlocal())
  return date.strftime("%Y/%m/%d %H:%M:%S")


def ReadComments(path):
  comments = []
  try:
    fd = os.open(path, os.O_RDONLY)
    fcntl.flock(fd, fcntl.LOCK_SH)
    input_file = os.fdopen(fd, "r")
    for line in input_file:
      fields = line.strip().split("\t")
      if len(fields) != 4: continue
      del fields[1]
      comments.append(fields)
    input_file.close()
  except:
    pass
  return comments


def WriteComment(path, date, addr, author, text):
  esc_text = EscapeCommentText(text)
  fields = [date, addr, author, esc_text]
  serialized = "\t".join(fields) + "\n"
  fd = os.open(path, os.O_WRONLY | os.O_APPEND | os.O_CREAT, 0o644)
  fcntl.flock(fd, fcntl.LOCK_EX)
  new_size = os.fstat(fd).st_size + len(serialized)
  if new_size > MAX_COMMENT_FILE_SIZE:
    return False
  output_file = os.fdopen(fd, "a")
  output_file.write(serialized)
  output_file.close()
  return True


def WriteHistory(path, date, resource, title, addr, author, text):
  short_title = re.sub(r"\s+", " ", title).strip()
  if len(short_title) > 64:
    short_title = short_title[:64] + "..."
  short_text = re.sub(r"\s+", " ", text).strip()
  if len(short_text) > 64:
    short_text = short_text[:64] + "..."
  fields = [date, resource, short_title, addr, author, short_text]
  serialized = "\t".join(fields) + "\n"
  limit_file_size = MAX_HISTORY_FILE_SIZE * 1.2 + 256
  fd = os.open(path, os.O_RDWR | os.O_CREAT, 0o644)
  fcntl.flock(fd, fcntl.LOCK_EX)
  new_size = os.fstat(fd).st_size + len(serialized)
  output_file = os.fdopen(fd, "r+")
  if new_size > limit_file_size:
    lines = []
    for line in output_file:
      lines.append(line.strip())
    lines.reverse()
    total_size = 0
    line_num = 0
    for line in lines:
      total_size += len(line) + 1
      if total_size > MAX_HISTORY_FILE_SIZE: break
      line_num += 1
    lines = lines[:line_num]
    lines.reverse()
    output_file.seek(0)
    output_file.truncate()
    for line in lines:
      output_file.write(line + "\n")
  else:
    output_file.seek(0, 2)
  output_file.write(serialized)
  output_file.close()
  return True


def DoListResources(resource_dir, params):
  names = []
  for name in os.listdir(resource_dir):
    if not name.endswith(".xhtml"): continue
    names.append(re.sub(r"\.xhtml$", "", name))
  resources = []
  for name in names:
    path = os.path.join(resource_dir, name + ".xhtml")
    meta = ReadResourceMeta(path)
    if not meta: return
    resources.append((name, meta[0], meta[1]))
  resources = sorted(resources, key=lambda x: x[0])
  print("Content-Type: text/plain; charset=UTF-8")
  print("")
  for resource in resources:
    print("\t".join(resource))


def CheckResourceName(resource):
  if not resource: return False
  if len(resource) > 256: return False
  if re.search(r"[/]", resource): return False
  return True


def DateToUnixTime(date):
  match = re.fullmatch(r"(\d{4})/(\d{2})/(\d{2}) (\d{2}):(\d{2}):(\d{2})", date)
  ts = datetime.datetime(
    int(match.group(1)), int(match.group(2)), int(match.group(3)),
    int(match.group(4)), int(match.group(5)), int(match.group(6)),
    tzinfo=dateutil.tz.tzlocal())
  return int(ts.timestamp())
  

def DoCountComments(resource_dir, comment_dir, params):
  p_resource = params.get("resource") or ""
  if not CheckResourceName(p_resource):
    PrintError(400, "Bad Request", "bad resource name")
    return
  res_path = os.path.join(resource_dir, p_resource + ".xhtml")
  meta = ReadResourceMeta(res_path)
  if not meta:
    PrintError(403, "Forbidden", "not an article resource")
    return
  cmt_path = os.path.join(comment_dir, p_resource + ".cmt")
  comments = ReadComments(cmt_path)
  count = len(comments)
  date = -1
  if comments:
    date = DateToUnixTime(comments[-1][0])
  print("Content-Type: text/plain; charset=UTF-8")
  print()
  print(count)
  print(date)


def DoListComments(resource_dir, comment_dir, params):
  p_resource = params.get("resource") or ""
  if not CheckResourceName(p_resource):
    PrintError(400, "Bad Request", "bad resource name")
    return
  res_path = os.path.join(resource_dir, p_resource + ".xhtml")
  meta = ReadResourceMeta(res_path)
  if not meta:
    PrintError(403, "Forbidden", "not an article resource")
    return
  cmt_path = os.path.join(comment_dir, p_resource + ".cmt")
  comments = ReadComments(cmt_path)
  print("Content-Type: text/plain; charset=UTF-8")
  print()
  for comment in comments:
    print("\t".join(comment))


def CalculateNonce(resource_id, comments):
  h = hashlib.new('md5')
  h.update((NONCE_SALT + resource_id).encode())
  for comment in comments:
    h.update("".join(comment).encode("UTF-8"))
  return h.hexdigest()


def DoGetNonce(resource_dir, comment_dir, params):
  p_resource = params.get("resource") or ""
  if not CheckResourceName(p_resource):
    PrintError(400, "Bad Request", "bad resource name")
    return
  res_path = os.path.join(resource_dir, p_resource + ".xhtml")
  meta = ReadResourceMeta(res_path)
  if not meta:
    PrintError(403, "Forbidden", "not an article resource")
    return
  cmt_path = os.path.join(comment_dir, p_resource + ".cmt")
  comments = ReadComments(cmt_path)
  nonce = CalculateNonce(p_resource, comments)
  print("Content-Type: text/plain; charset=UTF-8")
  print()
  print(nonce)


def DoPostComment(resource_dir, comment_dir, params, remote_addr):
  p_resource = params.get("resource") or ""
  p_author = params.get("author") or ""
  p_text = params.get("text") or ""
  p_nonce = params.get("nonce") or ""
  p_author = unicodedata.normalize("NFC", p_author)
  p_author = re.sub(r"\s+", " ", p_author).strip()
  p_text = unicodedata.normalize("NFC", p_text)
  p_text = re.sub(r"\n{3,}", "\n\n", p_text)
  p_text = re.sub(r"\t", "  ", p_text).strip()
  if not CheckResourceName(p_resource):
    PrintError(400, "Bad Request", "bad resource name")
    return
  if not p_author or len(p_author) > MAX_AUTHOR_LEN:
    PrintError(400, "Bad Request", "author is empty or too long")
    return
  if not p_text or len(p_text) > MAX_TEXT_LEN:
    PrintError(400, "Bad Request",  "text is empty or too long")
    return
  res_path = os.path.join(resource_dir, p_resource + ".xhtml")
  meta = ReadResourceMeta(res_path)
  if not meta:
    PrintError(403, "Forbidden", "not an article resource")
    return
  article_title = meta[0]
  cmt_path = os.path.join(comment_dir, p_resource + ".cmt")
  if CHECK_NONCE:
    comments = ReadComments(cmt_path)
    nonce = CalculateNonce(p_resource, comments)
    if p_nonce != nonce:
      PrintError(409, "Conflict", "nonce doesn't match")
      return
  date = GetCurrentDate()
  if not WriteComment(cmt_path, date, remote_addr, p_author, p_text):
    PrintError(500, "Internal Server Error", "writing comment failed")
    return
  hist_path = os.path.join(comment_dir, HISTORY_FILE)
  if not WriteHistory(hist_path, date, p_resource, article_title, remote_addr, p_author, p_text):
    PrintError(500, "Internal Server Error", "writing history failed")
    return
  print("Content-Type: text/plain; charset=UTF-8")
  print()
  print("Updated: " + p_resource)


def ReadHistory(path, num_max):
  comments = []
  try:
    fd = os.open(path, os.O_RDONLY)
    fcntl.flock(fd, fcntl.LOCK_SH)
    input_file = os.fdopen(fd, "r")
    for line in input_file:
      fields = line.strip().split("\t")
      if len(fields) != 6: continue
      del fields[3]
      comments.append(fields)
    input_file.close()
  except:
    pass
  comments.reverse()
  if num_max > 0 and len(comments) > num_max:
    comments = comments[:num_max]
  return comments


def DoListHistory(comment_dir, params):
  p_max = TextToInt(params.get("max") or "0")
  hist_path = os.path.join(comment_dir, HISTORY_FILE)
  comments = ReadHistory(hist_path, p_max)
  print("Content-Type: text/plain; charset=UTF-8")
  print()
  for comment in comments:
    print("\t".join(comment))


if __name__=="__main__":
  main()


# END OF FILE
