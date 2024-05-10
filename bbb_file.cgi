#! /usr/bin/python3
# -*- coding: utf-8 -*-
#--------------------------------------------------------------------------------------------------
# Manage files on the server
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
import math
import os
import re
import stat
import sys
import time
import unicodedata
import urllib
import urllib.parse


DATA_DIRS = [
  # Label, local path, URL path
  ("TUT", "/home/mikio/public/bikibikibob/data", "/bikibikibob/data"),
  ("HOGE", "hoge", "hoge"),
  ("ARTICLES", "input", "input"),
]
NUM_FILES_IN_PAGE = 10
MAX_FILE_SIZE = 1024 * 1024 * 256
IGNORE_FILENAME_REGEXES = [
  r"^\.", r"\.(cgi)$", "^(bbb)\.",
]
TEXT_EXTS = [
  "txt", "art", "tsv", "csv", "json",
  "html", "xhtml", "htm", "xml",
  "css", "js",
  "c", "cc", "cxx", "h", "hxx", "java", "py", "rb", "go", "pl", "pm", "lua",
]
IMAGE_EXTS = [
  "jpg", "jpeg", "png", "gif", "tif", "tiff", "svg",
  "pnm", "pbm", "pgm", "ppm", "bmp", "heic", "heif", "webp",
]
VIDEO_EXTS = [
  "mpg", "mpeg", "mp4", "mov", "qt", "wmv", "avi", "webm",
]
MAIN_HEADER_TEXT = """
<?xml version="1.0" encoding="UTF-8"?>
<html xmlns="http://www.w3.org/1999/xhtml" lang="en">
<head>
<meta charset="UTF-8"/>
<meta name="viewport" content="width=device-width,initial-scale=1"/>
<title>BikiBikiBob File</title>
<style type="text/css">/*<![CDATA[*/
html {
  margin: 0;
  padding: 0;
  background: #fff;
  text-align: center;
  font-size: 12pt;
  color: #111;
  text-justify: none;
  direction: ltr;
}
body {
  display: inline-block;
  width: 100%;
  text-align: left;
  line-height: 1.0;
}
h1 {
  font-size: 120%;
}
a {
  color: #02a;
  text-decoration: none;
}
a:hover {
  color: #03c;
  text-decoration: underline;
}
p.info {
  color: #01d;
}
p.error {
  color: #d00;
}
div.control_area {
  margin: 0.9ex 0;
}
table.control_table {
  margin: 0;
  border-collapse: collapse;
}
table.control_table td {
  padding: 0;
  vertical-align: top;
  white-space: nowrap;
  overflow: hidden;
  border: solid 1px #888;
}
table.control_table td.label {
  padding: 0.8ex 0.8ex;
  text-align: right;
  background: #f8f8f8;
}
table.control_table div.control_row {
  padding: 0.5ex 1.0ex;
}
table.control_table div.hidden_row {
  display: none;
  padding: 0.5ex 1.0ex;
}
div.pages_area {
  margin: 0.9ex 0;
}
div.pages_area a, div.pages_area span {
  display: inline-block;
  width: 3ex;
  text-align: center;
  white-space: nowrap;
  overflow: hidden;
  font-size: 90%;
  background: #f8f8f8;
  border: solid 1px #ddd;
  border-radious: 0.5ex;
}
div.pages_area span {
  color: #888;
}
table.file_table {
  margin: 0;
  border-collapse: collapse;
}
table.file_table td, table.file_table th {
  padding: 0.5ex 1.0ex;
  vertical-align: top;
  white-space: nowrap;
  overflow: hidden;
  border: solid 1px #888;
}
table.file_table th {
  font-weight: normal;
  background: #f8f8f8;
}
table.file_table td.num {
   text-align: right;
   font-size: 90%;
   color: #333;
}
table.file_table td.name {
  width: 24ex;
  font-size: 95%;
}
table.file_table td.attrs {
  font-size: 90%;
  color: #333;
}
table.file_table td.preview {
  width: 52ex;
}
table.file_table td.preview pre {
  margin: 0;
  padding: 0;
  width: 58ex;
  max-height: 30ex;
  overflow: hidden;
  font-size: 70%;
  color: #444;
  background: #eee;
}
table.file_table td.preview img {
  max-width: 100%;
  max-height: 30ex;
  overflow: hidden;
}
table.file_table td.preview video {
  max-width: 100%;
  max-height: 30ex;
  overflow: hidden;
}
table.file_table td.prview span {
  color: #888;
}
@media screen and (min-width:750px) {
  html {
    background: #eee;
  }
  body {
    display: inline-block;
    width: 700px;
    margin: 1ex 1ex;
    padding: 1ex 2ex;
    border: 1pt solid #ccc;
    border-radius: 1ex;
    text-align: left;
    background: #fff;
  }
}
/*]]>*/</style>
<script type="text/javascript">/*<![CDATA[*/
function main() {
  adjust_control();
}
function adjust_control() {
  const select_name = document.getElementById("select_name");
  const filename_row = document.getElementById("filename_row");
  if (select_name.value == "assign") {
    filename_row.style.display = "block";
  }
}
function check_upload() {
  const input_file = document.getElementById("input_file");
  const select_name = document.getElementById("select_name");
  const input_filename = document.getElementById("input_filename");
  if (input_file.value == "") {
    alert("No file is specified.");
    return false;
  }
  if (select_name.value == "assign" && input_filename.value.trim() == "") {
    alert("The filename is empty.");
    return false;
  }
  return true;
}
/*]]>*/</script>
</head>
<body onload="main();">
"""
MAIN_FOOTER_TEXT = """
</body>
</html>
"""


def main():
  request_method = os.environ.get("REQUEST_METHOD", "GET")
  script_filename = os.environ.get("SCRIPT_FILENAME", "")
  script_url = os.environ.get("REQUEST_SCHEME" or "http") + "://"
  script_url += os.environ.get("HTTP_HOST" or "localhost")
  script_url += os.environ.get("REQUEST_URI" or "/bbb_comment.cgi")
  script_url = re.sub(r"\?.*", "", script_url)
  base_dir = os.path.dirname(script_filename)
  data_dirs = []
  for label, path, url in DATA_DIRS:
    path = os.path.join(base_dir, path)
    data_dirs.append((label, path, url))
  form = cgi.FieldStorage()
  params = {}
  for key in form.keys():
    value = form[key]
    if hasattr(value, "filename") and value.filename:
      params[key] = value.value
      params[key + "_filename"] = value.filename
    if isinstance(value, list):
      params[key] = value[0].value
    else:
      params[key] = value.value
  p_action = params.get("action", "")
  print("Content-type: application/xhtml+xml")
  print("")
  print(MAIN_HEADER_TEXT.strip())
  P('<h1><a href="{}">BikiBikiBob Filer</a></h1>', script_url)
  if p_action == "upload":
    ProcessUpload(params, data_dirs)
  PrintControl(params, data_dirs)
  PrintDirectory(params, data_dirs)
  print(MAIN_FOOTER_TEXT.strip())

  
def TextToInt(text):
  try:
    return int(text)
  except:
    return 0


def TextToBool(text):
  if not text: return False
  return text.lower() in ["true", "yes", "on", "1"]

def esc(expr):
  if expr is None:
    return ""
  return html.escape(str(expr), True)


def P(*args, end="\n"):
  esc_args = []
  for arg in args[1:]:
    if isinstance(arg, str):
      arg = esc(arg)
    esc_args.append(arg)
  print(args[0].format(*esc_args), end=end)


def PrintError(message):
  P('<p class="error">{}</p>', message)


def NormalizeFilename(name):
  name = unicodedata.normalize("NFC", name)
  name = re.sub(r".*\\", "", name)
  name = re.sub(r".*/", "", name)
  name = re.sub(r"\s+", " ", name).strip()
  name = re.sub(r" ", "_", name)
  return name
  

def ProcessUpload(params, data_dirs):
  p_dir = TextToInt(params.get("dir", "1"))
  p_file = params.get("file")
  p_file_filename = NormalizeFilename(params.get("file_filename", ""))
  p_newname = NormalizeFilename(params.get("newname", ""))
  p_naming = params.get("naming", "local").strip()
  p_overwrite = params.get("overwrite", "force").strip()
  if p_dir < 1 or p_dir > len(data_dirs):
    PrintError("invalid dir parameter")
    return
  if not p_file or not p_file_filename:
    PrintError("upload failed: file is not specified")
    return
  if len(p_file) > MAX_FILE_SIZE:
    PrintError("upload failed: too large file")
    return
  dir_label, dir_path, dir_url = data_dirs[p_dir-1]
  if not os.path.isdir(dir_path):
    PrintError("upload failed: no such directory")
    return
  if p_naming == "date":
    date = datetime.datetime.fromtimestamp(time.time(), dateutil.tz.tzlocal())
    filename = date.strftime("%Y%m%d%H%M%S")
  elif p_naming == "assign":
    filename = p_newname
  else:
    filename = p_file_filename
  stem, ext = os.path.splitext(filename)
  if not stem:
    PrintError("upload failed: invalid filename")
    return
  if not ext:
    ext = os.path.splitext(p_file_filename)[1]
    if ext:
      filename = filename + ext
  for ignore_regex in IGNORE_FILENAME_REGEXES:
    if re.search(ignore_regex, filename):
      PrintError("upload failed: forbidden filename")
      return
  path = os.path.join(dir_path, filename)
  if os.path.exists(path):
    if p_overwrite == "rename":
      i = 2
      while True:
        if i >= 1000:
          PrintError("upload failed: too many filename duplications")
          return
        stem, ext = os.path.splitext(filename)
        new_filename = "{}-{:d}.{}".format(stem, i, ext)
        new_path = os.path.join(dir_path, new_filename)
        if not os.path.exists(new_path):
          filename = new_filename
          path = new_path
          break
        i += 1
    elif p_overwrite == "stop":
      PrintError("upload failed: duplicated filename")
      return
  try:
    with open(path, "wb") as out_file:
      out_file.write(p_file)
  except Exception as e:
    PrintError("upload failed: " + str(e))
    return
  P('<p class="info">The file "{}" has been uploaded successfully.</p>', filename)
  

def PrintControl(params, data_dirs):
  p_dir = TextToInt(params.get("dir", "1"))
  p_order = params.get("order", "date_r").strip()
  p_page = TextToInt(params.get("page", "1"))
  p_name = params.get("nameing", "local")
  p_over = params.get("overwrite", "force")
  P('<div class="control_area">')
  P('<table class="control_table">')
  P('<tr>')
  P('<td class="label">View:</td>')
  P('<td class="input">')
  P('<form name="view_form" method="GET" autocomplete="off">')
  P('<div class="control_row">')
  P('<select name="dir">')
  for i, (dir_label, dir_path, dir_url) in enumerate(data_dirs):
    P('<option value="{}"', i + 1, end="")
    if p_dir == i + 1: P(' selected="selected"', end="")
    P('>dir: {}</option>', dir_label)
  P('</select>')
  P('<select name="order">')
  for label, value in [("name asc", "name"), ("name desc", "name_r"),
                       ("size asc", "size"), ("size desc", "size_r"),
                       ("date asc", "date"), ("date desc", "date_r")]:
    P('<option value="{}"', value, end="")
    if p_order == value: P(' selected="selected"', end="")
    P('>order: {}</option>', label)
  P('</select>')
  P('<input type="submit" value="view"/>')
  P('</div>')
  P('</form>')  
  P('</td>')
  P('</tr>')
  P('<tr>')
  P('<td class="label">Upload:</td>')
  P('<td class="input">')
  P('<form name="upload_form" method="POST" enctype="multipart/form-data" autocomplete="off"'
    ' onsubmit="return check_upload();">')
  P('<div class="control_row">')
  P('<input type="file" id="input_file" name="file"/>')
  P('<select id="select_name" name="naming" onchange="adjust_control();">')
  for label, value in [("local", "local"), ("date", "date"), ("assign", "assign")]:
    P('<option value="{}"', value, end="")
    if p_name == value: P(' selected="selected"', end="")
    P('>name: {}</option>', label)
  P('</select>')
  P('<select name="overwrite">')
  for label, value in [("force", "force"), ("rename", "rename"), ("stop", "stop")]:
    P('<option value="{}"', value, end="")
    if p_over == value: P(' selected="selected"', end="")
    P('>overwrite: {}</option>', label)
  P('</select>')
  P('<input type="submit" value="upload"/>')
  P('</div>')
  P('<div id="filename_row" class="hidden_row">')
  P('Filename: <input type="input" id="input_filename" name="newname" value=""/>')
  P('</div>')
  P('<div class="hidden_row">')
  P('<p>hoge</p>')
  P('<input type="hidden" name="action" value="upload"/>')
  P('<input type="hidden" name="dir" value="{}"/>', p_dir)
  P('<input type="hidden" name="order" value="{}"/>', p_order)
  P('<input type="hidden" name="page" value="{}"/>', p_page)
  P('</div>')
  P('</form>')
  P('</td>')
  P('</tr>')
  P('</table>')
  P('</div>')
    

def SizeExpr(num):
  if num > 1024 * 1024 * 1024:
    return "{:.3f}GB".format(num / 1024 / 1024 / 1024)
  if num > 1024 * 1024:
    return "{:.3f}MB".format(num / 1024 / 1024)
  if num > 1024:
    return "{:.3f}KB".format(num / 1024)
  return "{:d}B".format(num)


def DateExpr(num):
  date = datetime.datetime.fromtimestamp(num, dateutil.tz.tzlocal())
  return date.strftime("%Y/%m/%d %H:%M:%S")


def PrintDirectory(params, data_dirs):
  p_dir = TextToInt(params.get("dir", "1"))
  p_order = params.get("order", "date_r").strip()
  p_page = TextToInt(params.get("page", "1"))
  if p_dir < 1 or p_dir > len(data_dirs):
    PrintError("invalid dir parameter")
    return
  if p_page < 1:
    PrintError("invalid page parameter")
    return
  dir_label, dir_path, dir_url = data_dirs[p_dir-1]
  if not os.path.isdir(dir_path):
    PrintError("no such directory")
    return
  data_files = []
  total_size = 0
  for name in sorted(os.listdir(dir_path)):
    ignore = False
    for ignore_regex in IGNORE_FILENAME_REGEXES:
      if re.search(ignore_regex, name):
        ignore = True
    if ignore: continue
    path = os.path.join(dir_path, name)
    st = os.stat(path)
    if not stat.S_ISREG(st.st_mode): continue
    data_file = {
      "name": name,
      "path": path,
      "stat": st,
      "ext": re.sub(r"^\.", "", os.path.splitext(name)[1].lower())
    }
    data_files.append(data_file)
    total_size += st.st_size
  if not data_files:
    PrintError("no files to show")
    return
  if p_order == "name":
    data_files = sorted(data_files, key=lambda x: x["name"])
  elif p_order == "name_r":
    data_files = sorted(data_files, key=lambda x: x["name"], reverse=True)
  elif p_order == "size":
    data_files = sorted(data_files, key=lambda x: (x["stat"].st_size, x["name"]))
  elif p_order == "size_r":
    data_files = sorted(data_files, key=lambda x: (x["stat"].st_size, x["name"]), reverse=True)
  elif p_order == "date":
    data_files = sorted(data_files, key=lambda x: (x["stat"].st_mtime, x["name"]))
  elif p_order == "date_r":
    data_files = sorted(data_files, key=lambda x: (x["stat"].st_mtime, x["name"]), reverse=True)
  num_files = len(data_files)
  start_index = NUM_FILES_IN_PAGE * (p_page - 1)
  data_files = data_files[start_index:start_index+NUM_FILES_IN_PAGE]
  P('<p>There are {:d} files with {}B in total.</p>',
    num_files, SizeExpr(total_size))
  def PrintPagenation():
    num_pages = math.ceil(num_files / NUM_FILES_IN_PAGE)
    P('<div class="pages_area">')
    for i in range(1, num_pages + 1):
      if i == p_page:
        P('<span>{}</span>', i)
      else:
        page_url = "?dir={}&order={}&page={}".format(p_dir, p_order, i)
        P('<a href="{}">{}</a>', page_url, i)
    P('</div>')
  PrintPagenation()
  P('<table class="file_table">')
  P('<tr>')
  P('<th>#</th>')
  P('<th>name</th>')
  P('<th>attributes</th>')
  P('<th>preview</th>')  
  P('</tr>')
  for i, data_file in enumerate(data_files):
    num = i + 1 + start_index
    name = data_file["name"]
    path = data_file["path"]
    st = data_file["stat"]
    ext = data_file["ext"]
    url = re.sub(r"/$", "", dir_url) + "/" + urllib.parse.quote(name)
    P('<tr>')
    P('<td class="num">{}</td>', num)
    P('<td class="name">')
    P('<div><a href="{}">{}</a></div>', url, name)
    P('</td>')
    P('<td class="attrs">')
    P('<div>{}</div>', SizeExpr(st.st_size))
    for date_expr in DateExpr(st.st_mtime).split(" "):
      P('<div>{}</div>', date_expr)
    P('</td>')
    P('<td class="preview">', end="")
    PrintPreview(ext, path, url)
    P('</td>', num)
    P('</tr>')    
  P('</table>')
  PrintPagenation()


def PrintPreview(ext, path, url):
  if ext in TEXT_EXTS:
    PrintPreviewText(path)
  elif ext in IMAGE_EXTS:
    PrintPreviewImage(url)
  elif ext in VIDEO_EXTS:
    PrintPreviewVideo(url)
  else:
    P('<span class="nopreview">-</span>')


def PrintPreviewText(path):
  P('<pre>', end="")
  with open(path) as input_file:
    num_line = 0
    for line in input_file:
      if num_line >= 10: break
      line = line.rstrip()[:64]
      if not line: continue
      num_line += 1
      P('{}', line)
  P('</pre>')


def PrintPreviewImage(url):
  P('<img src="{}"/>', url)


def PrintPreviewVideo(url):
  P('<video src="{}" controls="controls" preload="metadata"/>', url)


if __name__=="__main__":
  main()


# END OF FILE
