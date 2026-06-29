---
layout: Reference
monikers:
- word-js-preview
defaultMoniker: word-js-preview
versioningType: Ranged
title: Word.Comment class - Office Add-ins | Microsoft Learn
canonicalUrl: https://learn.microsoft.com/en-us/javascript/api/word/word.comment?view=word-js-preview
config_moniker_range: word-js-preview
uid: word!Word.Comment:class
package: word!
uhfHeaderId: MSDocsHeader-Dev_Office
breadcrumb_path: /javascript/office_js_breadcrumb/toc.json
ms.suite: office
ms.author: o365devx
apiPlatform: javascript
author: o365devx
ms.service: word
ms.subservice: add-ins
ms.topic: generated-reference
feedback_system: OpenSource
feedback_product_url: /answers/tags/321/office-development
ms.devlang: javascript
products:
- https://authoring-docs-microsoft.poolparty.biz/devrel/264d03ab-bab8-454b-a56c-0fedead7f602
- https://authoring-docs-microsoft.poolparty.biz/devrel/01e6eca5-e701-4cd9-a21f-56c9258f473e
locale: en-us
document_id: f6f898b0-8f16-7694-6d32-41c8efbd5031
document_version_independent_id: ae2938cd-ddb7-38b9-0234-6701a5e3404d
updated_at: 2026-06-17T03:15:00.0000000Z
original_content_git_url: https://github.com/OfficeDev/office-js-docs-reference/blob/live/docs/docs-ref-autogen/word/word/word.comment.yml
gitcommit: https://github.com/OfficeDev/office-js-docs-reference/blob/2072bfb27f28fbd8cbb01954f09a85b1da681ab2/docs/docs-ref-autogen/word/word/word.comment.yml
git_commit_id: 2072bfb27f28fbd8cbb01954f09a85b1da681ab2
default_moniker: word-js-preview
site_name: Docs
depot_name: MSDN.office-docs-ref-javascript
page_type: typescript
page_kind: class
description: 'Represents a comment in the document. '
toc_rel: ../office-js-docs-reference/toc.json
feedback_help_link_type: ''
feedback_help_link_url: ''
asset_id: api/word/word.comment
moniker_range_name: 537a0af654f9e6a4c7fb4acf3fd56e8e
monikers:
- word-js-preview
item_type: Content
source_path: docs/docs-ref-autogen/word/word/word.comment.yml
cmProducts: []
spProducts:
- https://authoring-docs-microsoft.poolparty.biz/devrel/264d03ab-bab8-454b-a56c-0fedead7f602
platformId: 743a5eec-cfa1-f033-053e-cc266aaf5bd2
---

# Word.Comment class

- Package:
    - [word](/en-us/javascript/api/word)

Represents a comment in the document.

- Extends
    - [OfficeExtension.ClientObject](/en-us/javascript/api/office/officeextension.clientobject)

## Remarks

[API set: WordApi 1.4](/en-us/javascript/api/requirement-sets/word/word-api-requirement-sets)

#### Used by

- [Word.CommentCollection](/en-us/javascript/api/word/word.commentcollection): [getFirst](/en-us/javascript/api/word/word.commentcollection#word-word-commentcollection-getfirst-member%281%29), [getFirstOrNullObject](/en-us/javascript/api/word/word.commentcollection#word-word-commentcollection-getfirstornullobject-member%281%29), [items](/en-us/javascript/api/word/word.commentcollection#word-word-commentcollection-items-member)
- [Word.CommentReply](/en-us/javascript/api/word/word.commentreply): [parentComment](/en-us/javascript/api/word/word.commentreply#word-word-commentreply-parentcomment-member)
- [Word.Range](/en-us/javascript/api/word/word.range): [insertComment](/en-us/javascript/api/word/word.range#word-word-range-insertcomment-member%281%29)

#### Examples

```TypeScript
// Link to full sample: https://raw.githubusercontent.com/OfficeDev/office-js-snippets/prod/samples/word/50-document/manage-comments.yaml

// Sets a comment on the selected content.
await Word.run(async (context) => {
  const text = (document.getElementById("comment-text") as HTMLInputElement).value;
  const comment: Word.Comment = context.document.getSelection().insertComment(text);

  // Load object to log in the console.
  comment.load();
  await context.sync();

  console.log("Comment inserted:", comment);
});
```

## Properties

| authorEmail | Gets the email of the comment's author. |
| --- | --- |
| authorName | Gets the name of the comment's author. |
| content | Specifies the comment's content as plain text. |
| contentRange | Specifies the comment's content range. |
| context | The request context associated with the object. This connects the add-in's process to the Office host application's process. |
| creationDate | Gets the creation date of the comment. |
| id | Gets the ID of the comment. |
| replies | Gets the collection of reply objects associated with the comment. |
| resolved | Specifies the comment thread's status. Setting to `true` resolves the comment thread. Getting a value of `true` means that the comment thread is resolved. |

## Methods

| delete() | Deletes the comment and its replies. |
| --- | --- |
| getRange() | Gets the range in the main document where the comment is on. |
| load(options) | Queues up a command to load the specified properties of the object. You must call `context.sync()` before reading the properties. |
| load(propertyNames) | Queues up a command to load the specified properties of the object. You must call `context.sync()` before reading the properties. |
| load(propertyNamesAndPaths) | Queues up a command to load the specified properties of the object. You must call `context.sync()` before reading the properties. |
| reply(replyText) | Adds a new reply to the end of the comment thread. |
| set(properties, options) | Sets multiple properties of an object at the same time. You can pass either a plain object with the appropriate properties, or another API object of the same type. |
| set(properties) | Sets multiple properties on the object at the same time, based on an existing loaded object. |
| toJSON() | Overrides the JavaScript `toJSON()` method in order to provide more useful output when an API object is passed to `JSON.stringify()`. (`JSON.stringify`, in turn, calls the `toJSON` method of the object that's passed to it.) Whereas the original `Word.Comment` object is an API object, the `toJSON` method returns a plain JavaScript object (typed as `Word.Interfaces.CommentData`) that contains shallow copies of any loaded child properties from the original object. |
| track() | Track the object for automatic adjustment based on surrounding changes in the document. This call is a shorthand for [context.trackedObjects.add(thisObject)](/en-us/javascript/api/office/officeextension.clientrequestcontext#office-officeextension-clientrequestcontext-trackedobjects-member). If you're using this object across `.sync` calls and outside the sequential execution of a ".run" batch, and get an "InvalidObjectPath" error when setting a property or invoking a method on the object, you need to add the object to the tracked object collection when the object was first created. If this object is part of a collection, you should also track the parent collection. |
| untrack() | Release the memory associated with this object, if it has previously been tracked. This call is shorthand for [context.trackedObjects.remove(thisObject)](/en-us/javascript/api/office/officeextension.clientrequestcontext#office-officeextension-clientrequestcontext-trackedobjects-member). Having many tracked objects slows down the host application, so please remember to free any objects you add, once you're done using them. You'll need to call `context.sync()` before the memory release takes effect. |

## Property Details

### authorEmail

Gets the email of the comment's author.

```typescript
readonly authorEmail: string;
```

#### Property Value

string

#### Remarks

[API set: WordApi 1.4](/en-us/javascript/api/requirement-sets/word/word-api-requirement-sets)

### authorName

Gets the name of the comment's author.

```typescript
readonly authorName: string;
```

#### Property Value

string

#### Remarks

[API set: WordApi 1.4](/en-us/javascript/api/requirement-sets/word/word-api-requirement-sets)

### content

Specifies the comment's content as plain text.

```typescript
content: string;
```

#### Property Value

string

#### Remarks

[API set: WordApi 1.4](/en-us/javascript/api/requirement-sets/word/word-api-requirement-sets)

#### Examples

```TypeScript
// Link to full sample: https://raw.githubusercontent.com/OfficeDev/office-js-snippets/prod/samples/word/50-document/manage-comments.yaml

// Edits the first active comment in the selected content.
await Word.run(async (context) => {
  const text = (document.getElementById("edit-comment-text") as HTMLInputElement).value;
  const comments: Word.CommentCollection = context.document.getSelection().getComments();
  comments.load("items");
  await context.sync();

  const firstActiveComment: Word.Comment = comments.items.find((item) => item.resolved !== true);
  if (!firstActiveComment) {
    console.warn("No active comment was found in the selection, so couldn't edit.");
    return;
  }

  firstActiveComment.content = text;

  // Load object to log in the console.
  firstActiveComment.load();
  await context.sync();

  console.log("Comment content changed:", firstActiveComment);
});
```

### contentRange

Specifies the comment's content range.

```typescript
contentRange: Word.CommentContentRange;
```

#### Property Value

[Word.CommentContentRange](/en-us/javascript/api/word/word.commentcontentrange)

#### Remarks

[API set: WordApi 1.4](/en-us/javascript/api/requirement-sets/word/word-api-requirement-sets)

#### Examples

```TypeScript
// Link to full sample: https://raw.githubusercontent.com/OfficeDev/office-js-snippets/prod/samples/word/50-document/manage-comments.yaml

// Gets the range of the first comment in the selected content.
await Word.run(async (context) => {
  const comment: Word.Comment = context.document.getSelection().getComments().getFirstOrNullObject();
  comment.load("contentRange");
  const range: Word.Range = comment.getRange();
  range.load("text");
  await context.sync();

  if (comment.isNullObject) {
    console.warn("No comments in the selection, so no range to get.");
    return;
  }

  console.log(`Comment location: ${range.text}`);
  const contentRange: Word.CommentContentRange = comment.contentRange;
  console.log("Comment content range:", contentRange);
});
```

### context

The request context associated with the object. This connects the add-in's process to the Office host application's process.

```typescript
context: RequestContext;
```

#### Property Value

[Word.RequestContext](/en-us/javascript/api/word/word.requestcontext)

### creationDate

Gets the creation date of the comment.

```typescript
readonly creationDate: Date;
```

#### Property Value

Date

#### Remarks

[API set: WordApi 1.4](/en-us/javascript/api/requirement-sets/word/word-api-requirement-sets)

### id

Gets the ID of the comment.

```typescript
readonly id: string;
```

#### Property Value

string

#### Remarks

[API set: WordApi 1.4](/en-us/javascript/api/requirement-sets/word/word-api-requirement-sets)

### replies

Gets the collection of reply objects associated with the comment.

```typescript
readonly replies: Word.CommentReplyCollection;
```

#### Property Value

[Word.CommentReplyCollection](/en-us/javascript/api/word/word.commentreplycollection)

#### Remarks

[API set: WordApi 1.4](/en-us/javascript/api/requirement-sets/word/word-api-requirement-sets)

#### Examples

```TypeScript
// Link to full sample: https://raw.githubusercontent.com/OfficeDev/office-js-snippets/prod/samples/word/50-document/manage-comments.yaml

// Gets the replies to the first comment in the selected content.
await Word.run(async (context) => {
  const comment: Word.Comment = context.document.getSelection().getComments().getFirstOrNullObject();
  comment.load("replies");
  await context.sync();

  if (comment.isNullObject) {
    console.warn("No comments in the selection, so no replies to get.");
    return;
  }

  const replies: Word.CommentReplyCollection = comment.replies;
  console.log("Replies to the first comment:", replies);
});
```

### resolved

Specifies the comment thread's status. Setting to `true` resolves the comment thread. Getting a value of `true` means that the comment thread is resolved.

```typescript
resolved: boolean;
```

#### Property Value

boolean

#### Remarks

[API set: WordApi 1.4](/en-us/javascript/api/requirement-sets/word/word-api-requirement-sets)

#### Examples

```TypeScript
// Link to full sample: https://raw.githubusercontent.com/OfficeDev/office-js-snippets/prod/samples/word/50-document/manage-comments.yaml

// Toggles Resolved status of the first comment in the selected content.
await Word.run(async (context) => {
  const comment: Word.Comment = context.document
    .getSelection()
    .getComments()
    .getFirstOrNullObject();
  comment.load("resolved");
  await context.sync();

  if (comment.isNullObject) {
    console.warn("No comments in the selection, so nothing to toggle.");
    return;
  }

  // Toggle resolved status.
  // If the comment is active, set as resolved.
  // If it's resolved, set resolved to false.
  const resolvedBefore = comment.resolved;
  console.log(`Comment Resolved status (before): ${resolvedBefore}`);
  comment.resolved = !resolvedBefore;
  comment.load("resolved");
  await context.sync();

  console.log(`Comment Resolved status (after): ${comment.resolved}`);
});
```

## Method Details

### delete()

Deletes the comment and its replies.

```typescript
delete(): void;
```

#### Returns

void

#### Remarks

[API set: WordApi 1.4](/en-us/javascript/api/requirement-sets/word/word-api-requirement-sets)

#### Examples

```TypeScript
// Link to full sample: https://raw.githubusercontent.com/OfficeDev/office-js-snippets/prod/samples/word/50-document/manage-comments.yaml

// Deletes the first comment in the selected content.
await Word.run(async (context) => {
  const comment: Word.Comment = context.document.getSelection().getComments().getFirstOrNullObject();
  comment.delete();
  await context.sync();

  if (comment.isNullObject) {
    console.warn("No comments in the selection, so nothing to delete.");
    return;
  }

  console.log("Comment deleted.");
});
```

### getRange()

Gets the range in the main document where the comment is on.

```typescript
getRange(): Word.Range;
```

#### Returns

[Word.Range](/en-us/javascript/api/word/word.range)

#### Remarks

[API set: WordApi 1.4](/en-us/javascript/api/requirement-sets/word/word-api-requirement-sets)

#### Examples

```TypeScript
// Link to full sample: https://raw.githubusercontent.com/OfficeDev/office-js-snippets/prod/samples/word/50-document/manage-comments.yaml

// Gets the range of the first comment in the selected content.
await Word.run(async (context) => {
  const comment: Word.Comment = context.document.getSelection().getComments().getFirstOrNullObject();
  comment.load("contentRange");
  const range: Word.Range = comment.getRange();
  range.load("text");
  await context.sync();

  if (comment.isNullObject) {
    console.warn("No comments in the selection, so no range to get.");
    return;
  }

  console.log(`Comment location: ${range.text}`);
  const contentRange: Word.CommentContentRange = comment.contentRange;
  console.log("Comment content range:", contentRange);
});
```

### load(options)

Queues up a command to load the specified properties of the object. You must call `context.sync()` before reading the properties.

```typescript
load(options?: Word.Interfaces.CommentLoadOptions): Word.Comment;
```

#### Parameters

- options
    - [Word.Interfaces.CommentLoadOptions](/en-us/javascript/api/word/word.interfaces.commentloadoptions)

Provides options for which properties of the object to load.

#### Returns

[Word.Comment](/en-us/javascript/api/word/word.comment)

### load(propertyNames)

Queues up a command to load the specified properties of the object. You must call `context.sync()` before reading the properties.

```typescript
load(propertyNames?: string | string[]): Word.Comment;
```

#### Parameters

- propertyNames
    - string | string[]

A comma-delimited string or an array of strings that specify the properties to load.

#### Returns

[Word.Comment](/en-us/javascript/api/word/word.comment)

### load(propertyNamesAndPaths)

Queues up a command to load the specified properties of the object. You must call `context.sync()` before reading the properties.

```typescript
load(propertyNamesAndPaths?: {
            select?: string;
            expand?: string;
        }): Word.Comment;
```

#### Parameters

- propertyNamesAndPaths
    - { select?: string; expand?: string; }

`propertyNamesAndPaths.select` is a comma-delimited string that specifies the properties to load, and `propertyNamesAndPaths.expand` is a comma-delimited string that specifies the navigation properties to load.

#### Returns

[Word.Comment](/en-us/javascript/api/word/word.comment)

### reply(replyText)

Adds a new reply to the end of the comment thread.

```typescript
reply(replyText: string): Word.CommentReply;
```

#### Parameters

- replyText
    - string

Reply text.

#### Returns

[Word.CommentReply](/en-us/javascript/api/word/word.commentreply)

#### Remarks

[API set: WordApi 1.4](/en-us/javascript/api/requirement-sets/word/word-api-requirement-sets)

#### Examples

```TypeScript
// Link to full sample: https://raw.githubusercontent.com/OfficeDev/office-js-snippets/prod/samples/word/50-document/manage-comments.yaml

// Replies to the first active comment in the selected content.
await Word.run(async (context) => {
  const text = (document.getElementById("reply-text") as HTMLInputElement).value;
  const comments: Word.CommentCollection = context.document.getSelection().getComments();
  comments.load("items");
  await context.sync();

  const firstActiveComment: Word.Comment = comments.items.find((item) => item.resolved !== true);
  if (firstActiveComment) {
    const reply: Word.CommentReply = firstActiveComment.reply(text);
    console.log("Reply added.");
  } else {
    console.warn("No active comment was found in the selection, so couldn't reply.");
  }
});
```

### set(properties, options)

Sets multiple properties of an object at the same time. You can pass either a plain object with the appropriate properties, or another API object of the same type.

```typescript
set(properties: Interfaces.CommentUpdateData, options?: OfficeExtension.UpdateOptions): void;
```

#### Parameters

- properties
    - [Word.Interfaces.CommentUpdateData](/en-us/javascript/api/word/word.interfaces.commentupdatedata)

A JavaScript object with properties that are structured isomorphically to the properties of the object on which the method is called.

- options
    - [OfficeExtension.UpdateOptions](/en-us/javascript/api/office/officeextension.updateoptions)

Provides an option to suppress errors if the properties object tries to set any read-only properties.

#### Returns

void

### set(properties)

Sets multiple properties on the object at the same time, based on an existing loaded object.

```typescript
set(properties: Word.Comment): void;
```

#### Parameters

- properties
    - [Word.Comment](/en-us/javascript/api/word/word.comment)

#### Returns

void

### toJSON()

Overrides the JavaScript `toJSON()` method in order to provide more useful output when an API object is passed to `JSON.stringify()`. (`JSON.stringify`, in turn, calls the `toJSON` method of the object that's passed to it.) Whereas the original `Word.Comment` object is an API object, the `toJSON` method returns a plain JavaScript object (typed as `Word.Interfaces.CommentData`) that contains shallow copies of any loaded child properties from the original object.

```typescript
toJSON(): Word.Interfaces.CommentData;
```

#### Returns

[Word.Interfaces.CommentData](/en-us/javascript/api/word/word.interfaces.commentdata)

### track()

Track the object for automatic adjustment based on surrounding changes in the document. This call is a shorthand for [context.trackedObjects.add(thisObject)](/en-us/javascript/api/office/officeextension.clientrequestcontext#office-officeextension-clientrequestcontext-trackedobjects-member). If you're using this object across `.sync` calls and outside the sequential execution of a ".run" batch, and get an "InvalidObjectPath" error when setting a property or invoking a method on the object, you need to add the object to the tracked object collection when the object was first created. If this object is part of a collection, you should also track the parent collection.

```typescript
track(): Word.Comment;
```

#### Returns

[Word.Comment](/en-us/javascript/api/word/word.comment)

### untrack()

Release the memory associated with this object, if it has previously been tracked. This call is shorthand for [context.trackedObjects.remove(thisObject)](/en-us/javascript/api/office/officeextension.clientrequestcontext#office-officeextension-clientrequestcontext-trackedobjects-member). Having many tracked objects slows down the host application, so please remember to free any objects you add, once you're done using them. You'll need to call `context.sync()` before the memory release takes effect.

```typescript
untrack(): Word.Comment;
```

#### Returns

[Word.Comment](/en-us/javascript/api/word/word.comment)

---

## Other Supported Versions

- [word-js-1.4-hidden-document](https://learn.microsoft.com/en-us/javascript/api/word/word.comment?view=word-js-1.4-hidden-document&accept=text/markdown)
- [word-js-1.4](https://learn.microsoft.com/en-us/javascript/api/word/word.comment?view=word-js-1.4&accept=text/markdown)
- [word-js-1.5-hidden-document](https://learn.microsoft.com/en-us/javascript/api/word/word.comment?view=word-js-1.5-hidden-document&accept=text/markdown)
- [word-js-1.5](https://learn.microsoft.com/en-us/javascript/api/word/word.comment?view=word-js-1.5&accept=text/markdown)
- [word-js-1.6](https://learn.microsoft.com/en-us/javascript/api/word/word.comment?view=word-js-1.6&accept=text/markdown)
- [word-js-1.7](https://learn.microsoft.com/en-us/javascript/api/word/word.comment?view=word-js-1.7&accept=text/markdown)
- [word-js-1.8](https://learn.microsoft.com/en-us/javascript/api/word/word.comment?view=word-js-1.8&accept=text/markdown)
- [word-js-1.9](https://learn.microsoft.com/en-us/javascript/api/word/word.comment?view=word-js-1.9&accept=text/markdown)
- [word-js-desktop-1.1](https://learn.microsoft.com/en-us/javascript/api/word/word.comment?view=word-js-desktop-1.1&accept=text/markdown)
- [word-js-desktop-1.2](https://learn.microsoft.com/en-us/javascript/api/word/word.comment?view=word-js-desktop-1.2&accept=text/markdown)
- [word-js-desktop-1.3](https://learn.microsoft.com/en-us/javascript/api/word/word.comment?view=word-js-desktop-1.3&accept=text/markdown)
- [word-js-desktop-1.4](https://learn.microsoft.com/en-us/javascript/api/word/word.comment?view=word-js-desktop-1.4&accept=text/markdown)
- [word-js-desktop-1.5](https://learn.microsoft.com/en-us/javascript/api/word/word.comment?view=word-js-desktop-1.5&accept=text/markdown)
- [word-js-online](https://learn.microsoft.com/en-us/javascript/api/word/word.comment?view=word-js-online&accept=text/markdown)
