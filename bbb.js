"use strict";

function main() {
  adjust_images();
  check_comments();
}

function adjust_images() {
  for (const area of document.getElementsByClassName("image_area")) {
    const area_width = area.getBoundingClientRect().width;
    const images = area.getElementsByClassName("emb_image");
    const max_area = area_width * area_width * 3 / 4;
    for (const image of images) {
      const image_area = image.width * image.height;
      if (image_area > max_area) {
        image.width = image.width * (max_area / image_area);
      }
    }
  }
}

function unescape_text(text) {
  text = text.replaceAll("\\n", "\n");
  text = text.replaceAll("\\\\", "\\");
  return text;
}

function check_comments() {
  const area = document.getElementById("comment_area");
  if (!area) return;
  const comment_url = area.dataset.commentUrl;
  const resource = area.dataset.resource;
  if (!comment_url || !resource) return;
  const request_url = comment_url + "?action=count-comments&resource=" + encodeURI(resource);
  const xhr = new XMLHttpRequest();
  xhr.onload = function() {
    if (xhr.status == 200) {
      const lines = xhr.responseText.split("\n");
      if (lines.length >= 2) {
        const count = parseInt(lines[0]);
        const date = parseInt(lines[1]);
        update_comment_banner(count, date);
      }
    }
  }
  xhr.open("GET", request_url, true);
  xhr.send();
}

function update_comment_banner(count, date) {
  const banner = document.getElementById("comment_banner");
  const comment_count = document.createElement("span");
  comment_count.className = "comment_count";
  comment_count.textContent = "(" + count + ")";
  banner.insertBefore(comment_count, null);
  if (count > 0) {
    const diff = new Date().getTime() / 1000 - date;
    if (diff < 60 * 60 * 24 * 2) {
      banner.classList.add("comment_recent");
    } else {
      banner.classList.add("comment_filled");
    }
  }
}

function render_comments() {
  const area = document.getElementById("comment_area");
  if (!area) return;
  const comment_url = area.dataset.commentUrl;
  const resource = area.dataset.resource;
  if (!comment_url || !resource) return;
  const banner = document.getElementById("comment_banner");
  banner.style.display = "none";
  const request_url = comment_url + "?action=list-comments&resource=" + encodeURI(resource);
  const xhr = new XMLHttpRequest();
  xhr.onload = function() {
    if (xhr.status == 200) {
      const comments = [];
      for (const line of xhr.responseText.split("\n")) {
        const fields = line.split("\t");
        if (fields.length != 4) continue;
        const comment = {}
        comment.date = fields[0];
        comment.addr = fields[1];
        comment.author = fields[2];
        comment.text = unescape_text(fields[3]);
        comments.push(comment);
      }
      update_comment_list(comments)
      window.scrollTo(0, document.body.scrollHeight);
    }
  }
  xhr.open("GET", request_url, true);
  xhr.send();
}

function update_comment_list(comments) {
  const pane = document.getElementById("comment_list");
  pane.style.display = "block";
  pane.innerHTML = "";
  for (const comment of comments) {
    const comment_item = document.createElement("div");
    comment_item.className = "comment_item";
    const comment_date = document.createElement("div");
    comment_date.className = "comment_date";
    comment_date.textContent = comment.date;
    comment_item.insertBefore(comment_date, null);
    const comment_author = document.createElement("div");
    comment_author.className = "comment_author";
    comment_author.textContent = comment.author;
    comment_item.insertBefore(comment_author, null);
    const comment_text = document.createElement("div");
    comment_text.className = "comment_text";
    comment_text.textContent = comment.text;
    comment_item.insertBefore(comment_text, null);
    pane.insertBefore(comment_item, null);
  }
  if (comments.length < 1) {
    const comment_item = document.createElement("div");
    comment_item.className = "comment_item";
    const comment_message = document.createElement("div");
    comment_message.className = "comment_message";
    comment_message.textContent = "(no comments yet)";
    comment_item.insertBefore(comment_message, null);
    pane.insertBefore(comment_item, null);
  }
  const form = document.getElementById("comment_form");
  form.style.display = "block";  
}

function post_comment() {
  const area = document.getElementById("comment_area");
  if (!area) return;
  const comment_url = area.dataset.commentUrl;
  const resource = area.dataset.resource;
  const author_elem = document.getElementById("comment_author");
  const text_elem = document.getElementById("comment_text");
  const author = author_elem.value;
  const text = text_elem.value;
  if (author.trim().length < 1) {
    show_comment_message("empty author");
    return;
  }
  if (text.trim().length < 1) {
    show_comment_message("empty text");
    return;
  }
  if (text.length > 3000) {
    show_comment_message("too long text (must be up to 3000 characters)");
    return;
  }
  let current_time = new Date().getTime() / 1000;
  if (area.last_post_time && current_time - area.last_post_time < 10) {
    show_comment_message("too quick; please wait for a moment");
    return;
  }
  show_comment_message("checking the nonce ...");
  const request_url = comment_url + "?action=get-nonce&resource=" + encodeURI(resource);
  const xhr = new XMLHttpRequest();
  xhr.onload = function() {
    if (xhr.status == 200) {
      const nonce = xhr.responseText.trim();
      post_comment_second(comment_url, resource, author, text, nonce);
    } else {
      show_comment_message("cannot get the nonce");
    }
  }
  xhr.open("GET", request_url, true);
  xhr.send();
}

function post_comment_second(comment_url, resource, author, text, nonce) {
  const area = document.getElementById("comment_area");
  const text_elem = document.getElementById("comment_text");
  show_comment_message("posting the comment ...");
  const params = [];
  params.push("action=post-comment");
  params.push("resource=" + encodeURI(resource));
  params.push("author=" + encodeURI(author));
  params.push("text=" + encodeURI(text));
  params.push("nonce=" + encodeURI(nonce));
  const joined_params = params.join("&");
  const xhr = new XMLHttpRequest();
  xhr.onload = function() {
    if (xhr.status == 200) {
      show_comment_message("posted successfully");
      text_elem.value = "";
      let current_time = new Date().getTime() / 1000;
      area.last_post_time = current_time;
      render_comments();
    } else if (xhr.status == 409) {
      show_comment_message("posting conflicted; please try again");
    }
  }
  xhr.open("POST", comment_url, true);
  xhr.setRequestHeader("Content-Type", "application/x-www-form-urlencoded");
  xhr.send(joined_params);
}

function show_comment_message(message) {
  const message_elem = document.getElementById("comment_message");
  message_elem.textContent = message;
  if (message) {
    message_elem.style.display = "inline";
  } else {
    message_elem.style.display = "none";
  }
  if (message_elem.last_cleaner) {
    clearTimeout(message_elem.last_cleaner);
  }
  message_elem.last_cleaner = setTimeout(function() {
    message_elem.style.display = "none";
  }, 3000);
}

// END OF FILE
