"use strict";

function main() {
  adjust_images();
  adjust_columns();
  check_comments();
  render_comment_history();
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

function adjust_columns() {
  for (const column of document.getElementsByClassName("column_overt")) {
    column.style.display = "block";
  }
  for (const trigger of document.getElementsByClassName("column_overt_trigger")) {
    trigger.style.display = "none";
  }
}

function open_column(trigger_elem) {
  const column_id = trigger_elem.dataset.columnId;
  const column = document.getElementById(column_id);
  column.style.display = "block";
  trigger_elem.style.display = "none";
}

function close_column(close_elem) {
  const column = close_elem.parentElement;
  const trigger_id = column.id.replace("column", "column_trigger");
  const trigger_elem = document.getElementById(trigger_id);
  column.style.display = "none";
  trigger_elem.style.display = "inline-block";
}

function search_tags(tag_elem) {
  const result_pane = document.getElementById("tags_result");
  const self_resource = result_pane.dataset.resource;
  const tag = tag_elem.textContent;
  if (result_pane.last_tag == tag) {
    result_pane.style.display = "none";
    result_pane.innerHTML = "";
    result_pane.last_tag = null;
    return;
  }
  const index_url =
        document.location.toString().replace(/\/[^\/]+$/, "/") + "__toc__.tsv";
  const xhr = new XMLHttpRequest();
  xhr.onload = function() {
    if (xhr.status == 200) {
      const resources = [];
      for (const line of xhr.responseText.split("\n")) {
        const fields = line.split("\t");
        if (fields.length < 3) continue;
        const res_tags = fields[3].split(",");
        for (let res_tag of res_tags) {
          res_tag = res_tag.trim();
          if (res_tag == tag) {
            const resource = {};
            resource.name = fields[0];
            resource.title = fields[1];
            resource.date = fields[2];
            resource.is_self = resource.name == self_resource;
            resources.push(resource);
          }
        }
        result_pane.last_tag = tag;
        update_tag_result(result_pane, resources);
      }
    }
  };
  xhr.onerror = function() {
    alert('networking error while getting tag index');
  };
  xhr.open("GET", index_url, true);
  xhr.setRequestHeader("Cache-Control", "no-cache");
  xhr.send();
}

function update_tag_result(result_pane, resources) {
  result_pane.style.display = "block";
  result_pane.innerHTML = "";
  for (const resource of resources) {
    const tag_result_item = document.createElement("a");
    tag_result_item.className = "tags_result_item";
    tag_result_item.textContent = resource.title.length > 0 ?
      resource.title : resource.name;
    tag_result_item.href = "./" + encodeURI(resource.name) + ".xhtml";
    if (resource.is_self) {
      tag_result_item.classList.add("tags_result_item_self");
    } else {
      tag_result_item.classList.add("tags_result_item_other");
    }
    result_pane.insertBefore(tag_result_item, null);
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
  };
  xhr.onerror = function() {
    alert('networking error while counting comments');
  };
  xhr.open("GET", request_url, true);
  xhr.setRequestHeader("Cache-Control", "no-cache");
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
        if (fields.length != 3) continue;
        const comment = {}
        comment.date = fields[0];
        comment.author = fields[1];
        comment.text = unescape_text(fields[2]);
        comments.push(comment);
      }
      update_comment_list(comments)
      window.scrollTo(0, document.body.scrollHeight);
    }
  };
  xhr.onerror = function() {
    alert('networking error while getting comments');
  };
  xhr.open("GET", request_url, true);
  xhr.setRequestHeader("Cache-Control", "no-cache");
  xhr.send();
  const author_elem = document.getElementById("comment_author");
  if (author_elem.value.length == 0) {
    const saved_user_name = load_user_name();
    if (saved_user_name) {
      author_elem.value = saved_user_name;
    }
  }
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
  if (author.length > 30) {
    show_comment_message("too long name (must be up to 30 characters)");
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
  };
  xhr.onerror = function() {
    alert('networking error while checking the nonce');
  };
  xhr.open("GET", request_url, true);
  xhr.setRequestHeader("Cache-Control", "no-cache");
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
      save_user_name(author);
    } else if (xhr.status == 409) {
      show_comment_message("posting conflicted; please try again");
    } else {
      show_comment_message("posting failed");
    }
  }
  xhr.onerror = function() {
    alert('networking error while posting the comment');
  }
  xhr.open("POST", comment_url, true);
  xhr.setRequestHeader("Content-Type", "application/x-www-form-urlencoded");
  xhr.setRequestHeader("Cache-Control", "no-cache");
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

function save_user_name(name) {
  if (!localStorage) return;
  return localStorage.setItem("user_name", name);
}

function load_user_name() {
  if (!localStorage) return null;
  return localStorage.getItem("user_name");
}

function render_comment_history() {
  for (const area of document.getElementsByClassName("comment_history_area")) {
    const comment_url = area.dataset.commentUrl;
    const max = area.dataset.commentMax;
    let perpage = area.dataset.commentPerpage;
    if (perpage < 1) {
      perpage = 100;
    }
    const request_url = comment_url + "?action=list-history&max=" + max;
    const xhr = new XMLHttpRequest();
    xhr.onload = function() {
      if (xhr.status == 200) {
        const comments = [];
        const lines = xhr.responseText.split("\n");
        if (lines.length < 1) {
          return;
        }
        const num_comments = parseInt(lines[0]);
        for (let i = 1; i < lines.length; i++) {
          const line = lines[i];
          const fields = line.split("\t");
          if (fields.length != 5) continue;
          const comment = {}
          comment.date = fields[0];
          comment.resource = fields[1];
          comment.title = fields[2];
          comment.author = fields[3];
          comment.text = fields[4];
          comments.push(comment);
        }
        update_comment_history(area, num_comments, comments, perpage, 1);
      }
    };
    xhr.onerror = function() {
      alert('networking error while getting comment history');
    };
    xhr.open("GET", request_url, true);
    xhr.setRequestHeader("Cache-Control", "no-cache");
    xhr.send();
  }
}

function update_comment_history(area, num_comments, comments, perpage, page) {
  area.innerHTML = "";
  if (comments.length < 1) {
    const history_message = document.createElement("div");
    history_message.className = "history_message";
    history_message.textContent = "(no comments yet)";
    area.insertBefore(history_message, null);
    return;
  }
  const history_meta = document.createElement("div");
  history_meta.className = "history_meta";
  const history_num = document.createElement("span");
  history_num.className = "history_num";
  history_num.textContent = num_comments + " comments in history";
  history_meta.insertBefore(history_num, null);
  area.insertBefore(history_meta, null);
  if (comments.length > perpage) {
    const history_control = document.createElement("div");
    history_control.className = "history_control";
    const history_prev = document.createElement("span");
    history_prev.className = "history_step";
    if (page > 1) {
      history_prev.classList.add("history_step_active");
      history_prev.onclick = function() {
        update_comment_history(area, num_comments, comments, perpage, page - 1);
      }
    } else {
      history_prev.classList.add("history_step_inactive");
    }
    history_prev.textContent = "←";
    history_control.insertBefore(history_prev, null);
    const history_next = document.createElement("span");
    history_next.className = "history_step";
    if (page * perpage < comments.length ) {
      history_next.classList.add("history_step_active");
      history_next.onclick = function() {
        update_comment_history(area, num_comments, comments, perpage, page + 1);
      }
    } else {
      history_next.classList.add("history_step_inactive");
    }
    history_next.textContent = "→";
    history_control.insertBefore(history_next, null);
    area.insertBefore(history_control, null);
  }
  const history_list = document.createElement("ul");
  let end_index = Math.min(page * perpage, comments.length);
  for (let index = (page - 1) * perpage; index < end_index; index++) {
    const comment = comments[index];
    const history_item = document.createElement("li");
    history_item.className = "history_item";
    const history_author = document.createElement("span");
    history_author.className = "history_author";
    history_author.textContent = comment.author;
    history_item.insertBefore(history_author, null);
    history_item.insertBefore(document.createTextNode(": "), null);
    const history_text = document.createElement("span");
    history_text.className = "history_text";
    history_text.textContent = '"' + comment.text + '"';
    history_item.insertBefore(history_text, null);
    history_item.insertBefore(document.createTextNode(" - "), null);
    const history_resource = document.createElement("a");
    history_resource.className = "history_resource";
    if (comment.title == "") {
      history_resource.textContent = comment.resource;
    } else {
      history_resource.textContent = '"' + comment.title + '"';
    }
    history_resource.href = "./" + comment.resource + ".xhtml";
    history_item.insertBefore(history_resource, null);
    history_item.insertBefore(document.createTextNode(" - "), null);
    const history_date = document.createElement("span");
    history_date.className = "history_date";
    history_date.textContent = comment.date;
    history_item.insertBefore(history_date, null);
    history_list.insertBefore(history_item, null);
  }
  area.insertBefore(history_list, null);
}

function search_fulltext(elem) {
  let search_area = null;
  while (elem) {
    if (elem.className == "search_area") {
      search_area = elem;
      break;
    }
    elem = elem.parentElement;
  }
  if (!search_area) return;
  const search_url = search_area.dataset.searchUrl;
  const max = search_area.dataset.searchMax;
  let perpage = search_area.dataset.searchPerpage;
  if (perpage < 1) {
    perpage = 100;
  }
  const query = search_area.getElementsByClassName("search_query")[0].value.trim();
  const order = search_area.getElementsByClassName("search_order")[0].value.trim();
  const result_area = search_area.getElementsByClassName("search_result")[0];
  result_area.style.display = "none";
  result_area.innerHTML = "";
  if (query.length == 0) {
    return;
  }
  const request_url = search_url + "?query=" + encodeURI(query) +
        "&order=" + encodeURI(order) + "&max=" + max;
  const xhr = new XMLHttpRequest();
  xhr.onload = function() {
    if (xhr.status == 200) {
      const docs = [];
      const lines = xhr.responseText.split("\n");
      if (lines.length < 1) {
        return;
      }
      const num_docs = parseInt(lines[0]);
      for (let i = 1; i < lines.length; i++) {
        const line = lines[i];
        const fields = line.split("\t");
        if (fields.length < 4) continue;
        const snippets = [];
        for (let i = 4; i < fields.length; i++) {
          snippets.push(fields[i]);
        }
        const doc = {
          "name": fields[0],
          "score": parseFloat(fields[1]),
          "title": fields[2],
          "date": fields[3],
          "snippets": fields.slice(4),
        };
        docs.push(doc);
      }
      update_search_result(result_area, num_docs, docs, perpage, 1);
    }
  };
  xhr.onerror = function() {
    alert('networking error while getting comment history');
  };
  xhr.open("GET", request_url, true);
  xhr.setRequestHeader("Cache-Control", "no-cache");
  xhr.send();
}

function update_search_result(result_area, num_docs, docs, perpage, page) {
  result_area.style.display = "block";
  result_area.innerHTML = "";
  if (docs.length < 1) {
    const search_result_message = document.createElement("div");
    search_result_message.className = "search_result_message";
    search_result_message.textContent = "(no matching items)";
    result_area.insertBefore(search_result_message, null);
    return;
  }
  const search_meta = document.createElement("div");
  search_meta.className = "search_meta";
  const search_num = document.createElement("span");
  search_num.className = "search_num";
  search_num.textContent = num_docs + " matching articles";
  search_meta.insertBefore(search_num, null);
  result_area.insertBefore(search_meta, null);
  if (docs.length > perpage) {
    const search_control = document.createElement("div");
    search_control.className = "search_control";
    const search_prev = document.createElement("span");
    search_prev.className = "search_step";
    if (page > 1) {
      search_prev.classList.add("search_step_active");
      search_prev.onclick = function() {
        update_search_result(result_area, num_docs, docs, perpage, page - 1);
      }
    } else {
      search_prev.classList.add("search_step_inactive");
    }
    search_prev.textContent = "←";
    search_control.insertBefore(search_prev, null);
    const search_next = document.createElement("span");
    search_next.className = "search_step";
    if (page * perpage < docs.length ) {
      search_next.classList.add("search_step_active");
      search_next.onclick = function() {
        update_search_result(result_area, num_docs, docs, perpage, page + 1);
      }
    } else {
      search_next.classList.add("search_step_inactive");
    }
    search_next.textContent = "→";
    search_control.insertBefore(search_next, null);
    result_area.insertBefore(search_control, null);
  }
  let end_index = Math.min(page * perpage, docs.length);
  for (let index = (page - 1) * perpage; index < end_index; index++) {
    const doc = docs[index];
    const search_result_item = document.createElement("div");
    search_result_item.className = "search_result_item";
    const title = doc.title.length > 0 ? doc.title : doc.name;
    const url = doc.name + ".xhtml";
    const search_result_title = document.createElement("div");
    const search_result_link = document.createElement("a");
    search_result_link.textContent = title;
    search_result_link.href = url;
    search_result_link.className = "search_result_link";
    search_result_title.insertBefore(search_result_link, null);
    if (doc.date.length > 0) {
      const search_result_date = document.createElement("span");
      search_result_date.textContent = "(" + doc.date + ")";
      search_result_date.className = "search_result_date";
      search_result_title.insertBefore(search_result_date, null);
    }
    search_result_item.insertBefore(search_result_title, null);
    if (doc.snippets.length > 0) {
      const search_result_snippet_list = document.createElement("div");
      search_result_snippet_list.className = "search_result_snippet_list";
      let i = 0;
      for (const snippet of doc.snippets) {
        if (i > 0) {
          const search_result_snippet_delim = document.createElement("span");
          search_result_snippet_delim.textContent = " ◇ ";
          search_result_snippet_delim.className = "search_result_snippet_delim";
          search_result_snippet_list.insertBefore(search_result_snippet_delim, null);
        }
        const search_result_snippet = document.createElement("span");
        search_result_snippet.textContent = snippet;
        search_result_snippet.className = "search_result_snippet";
        search_result_snippet_list.insertBefore(search_result_snippet, null);
        i++;
      }
      search_result_item.insertBefore(search_result_snippet_list, null);
    }
    result_area.insertBefore(search_result_item, null);
  }
}

// END OF FILE
