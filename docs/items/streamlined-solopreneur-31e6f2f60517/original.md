**[00:00:00]** Before I had kids, one of my favorite things to do was go to concerts, and I would travel to go to concerts. concerts. And one time when I was in upstate New York, we were seeing one of my favorite bands, and we decided to fuel up before the show.

**[00:00:00]** And we didn't go to dinner or order in. No, I bought a box of Pop-Tarts, and I decided I wanted to have a warm Pop-Tart. And since we didn't have a toaster in the room, I decided to microwave that Pop-Tart. The instructions say to microwave a Pop-Tart for three seconds. I decided to do it for two minutes. And as you can imagine, the room filled with smoke, the smoke alarm went off, and I looked like an idiot. The point is that I used a tool that technically could do the job, but it was far too powerful, and so it wasn't the right tool for the job. And that's what I wanna talk about today. When we think about automation tools like Zapier and Make versus AI skills, like the ones you see in Claude or n8n or ChatGPT.

**[00:00:00]** Hey everybody, and welcome to the Streamlined Solopreneur, where I help overwhelmed coaches, consultants, and service providers build systems so their business doesn't depend on them. Each week I share one practical idea to help you beat overwhelm, get your time back, and run your business without sacrificing the rest of your life or your health.

**[00:00:00]** All right. So, today I do wanna talk about kind of AI and automation. People are starting to use these terms interchangeably where you mention automation, and they immediately associate AI with those things. And they are not the same at all, right?

**[00:00:00]** Automation, what I will refer to as deterministic automation. This is a term that I saw on LinkedIn from a woman who works at Zapier named, uh, Emily Mabie. That's M-A-B-I-E and I, so I hope I'm saying that right. But I absolutely love this framing for tools like Zapier and Make, because it makes perfect sense. You are essentially writing a very simple deterministic program. I have this thing that happens, and based on a small set of criteria, I want this to be the outcome. So deterministic automation is exactly that. You know the input, you know the output, and it's going to be incredibly consistent.

**[00:00:00]** When we look at AI tools, large language models, or what people are calling AI agents a term I don't really like to use, but it's the one that we're using. I'll get used to it, just like I got used to the word webinar. Those are much more broad. They employ deeper algorithms, and they have- I'm not gonna say they think or they do their own thing; they are more autonomous, though.

**[00:00:00]** Their underlying programming is such that it's not as deterministic as something like Zapier. You can run the same thing multiple times and get potentially different outputs based on the interpretive algorithm underneath the large language model.

**[00:00:00]** And so both of these can do similar things. I do have things I automate with the scheduled skills in Claude, but I am not going to treat those things the same because one is deterministic in that I always know what's going to happen when this automation runs, and I know what is going to make this automation run.

**[00:00:00]** And there is one that is, let's call it like the interpretive algorithm of AI. I don't like using the term interpretive here, 'cause interpretation implies some sort of thinking, but it's an algorithm that runs a bunch of times underneath the hood to get you what it believes is the outcome you want. And so again, that could look different for each run. 
So let's kind of dive into both of these things, and then I'll give you a really clear example of why they are different, and then how you can figure out what to use for what task.

**[00:00:00]** Deterministic automation is much more predictable, and I think it should be used most of the time. When you are creating these automations, you want your business to be predictable. And so when you're setting up automations to do something such that when X happens, I want Y to happen, you can trust that with deterministic automation. As long as the automation is running, you are going to get the expected outcome.

**[00:00:00]** The other side of this is that with deterministic automations, errors are much more clearly errors, right? So if an automation is not on that, the automation is not going to run. If the expected result of the automation doesn't happen, Zapier will email you and tell you there was some sort of issue.

**[00:00:00]** That isn't always going to be the case with AI, right? It will do its own interpretation of the task you want it to perform. And you know, because they are sycophantic, right? Because they want to appease you. If you push back, it'll be like, you're absolutely right. Whereas with Zapier, it's like, you told me to do this, and this happened or this didn't happen. So there is an error, right? So that's deterministic automation.

**[00:00:00]** AI is good for more interpretive automated tasks, right? So there are some things like my inbox sweep, right? Which will look at my emails and figure out my tasks, or my call debrief skill, which will do the same thing. They have a little bit more latitude for what they're going to interpret as a task or add to the summary, but as a result, the results are less predictable and more subject to change.

**[00:00:00]** So for a while, my inbox sweep was running perfectly fine. The things I expected to get added got added, but recently it ran, and I felt like it was missing a couple of things. And so then I had to go in and tweak the skill. And so is that something that you wanna be doing all the time with all of your tasks, right? And, and here's an even clearer example of that.

**[00:00:00]** My copy editor skill changed dramatically with Claude Opus five. I have it proofread my work and then I have it look for structural issues, right? Which I'm not saying like, tell me if this is wrong or what do you think I'm saying? Does the thing I set up in the beginning eventually get paid off? Am I wording things in a way that a human would understand?

**[00:00:00]** It got very opinionated with those structural notes, right? It referred to something that I referred to AI doing a rant, and I'm like, that is not your job, right? And it was like, you're absolutely right. So I had to tweak that skill. I've never had to adjust a Zap like that, right? In fact, when Notion changed the way they connected to Zapier, I didn't make the updates right away, but the old way worked for a while. So, even immediately after the change, my zaps still worked as expected, right? Whereas with a large language model, when the model changes your skills, your automations, your interpretive automations might dramatically change.

**[00:00:00]** And so then I had to spend a couple of hours double-checking some of these things. A couple, not all in a row, but over a few days, double-checking these things and making sure I was getting the results that I still expected.

**[00:00:00]** Further, when Notion did change the way that they connected to Zapier, the change was very well documented from both the Zapier side and the Notion side, and very well communicated from both Zapier side and Notion's side with large language models, what I'm calling interpretive automation. it may not even think it messed up, or it may not even know it messed up, that it aired out until you point it out, and then it, by default, agrees with you. Don't get me wrong, it's really good for a lot of things, the interpretive automations, but when your business is relying on something, it should, in my opinion, my very strong opinion be deterministic AI.

**[00:00:00]** So how do you figure out when to use deterministic automation versus interpretive automation? Well, I've talked about deterministic automation before, right? There are four components to deterministic automation. You have the trigger; that's the inciting incident. You have one or more actions, right? So when the trigger happens, I want these things to happen. You have timing, which is how often the automation should run, and you have conditions, which could slightly change that deterministic automation: if it's sunset in December, turn the Christmas lights on. But if it's sunset in the summer, I don't want my Christmas lights turned on, right? That's a very simple deterministic automation. There is some trigger sunset; there is some condition, is it December?

**[00:00:00]** And then there is the action of turning the lights on. So that's deterministic. If you want consistency, and it's a routine that's going to run regularly. If there are no tasks or actions that need to be left to interpretation, you should use deterministic automation. This is going to be true for most automations in your business.

**[00:00:00]** When should you use AI or what I'm calling interpretive automation?

**[00:00:00]** Well, when there are things left for interpretation, or there is not a deterministic automation that could be run as easily or as consistently. So a couple of examples here, right?

**[00:00:00]** My daily call debrief is going to run every night at 6:00 PM. It's going to look at all the calls I had in Gemini and Fathom, summarize them, and add tasks to Todoist. This is interpretive because it's taking the text of those calls and figuring out what I need to do and then adding them to Todoist. It's going to over-index, which is my preference.

**[00:00:00]** Another one is Kit newsletter scoring, right? That's going to run every Wednesday at 9:30 PM. It's going to look at the last couple of newsletters I sent, and then, based on a scoring rubric that I came up with, give it a score. Is this something that deterministic automation can do? Yes, kind of. I'd have to write a lot of code into Zapier to do that, though.

**[00:00:00]** And the same thing is true of my Streamlined podcaster weekly publisher, right? So what this does is it looks in Notion for any episodes that are marked ready for publish, grabs the transcript, creates the show notes, pushes everything to rss.com, and then schedules it for the scheduled day. And then I review everything the next day because it runs on Wednesdays; I check it Thursdays, and the new episodes go out Friday. So I have at least one buffer day to check those episodes.

**[00:00:00]** Is this something that you can do with Zapier? Technically yes. Right? Zapier has webhooks and you can 
use it to connect to the rss.com API. But with Claude, I was basically able to point it at the documentation, then it, it wrote a small application that runs on my computer. So that is technically could be deterministic, right? When I mark an episode as ready for publish, push it to rss.com.

**[00:00:00]** But in my estimation, it does run more reliably as a tiny application on my computer every Wednesday. And I think that's the other side of it, right? Is that a lot of it that is not being left up to Claude's interpretation?

**[00:00:00]** Claude is grabbing all the parts and then running this code that theoretically ha has not changed. That's not going to change when the model changes. And that's really the main thing that you should be thinking about here: when the AI model changes, is this going to have a potentially devastating impact on the things I'm doing?

**[00:00:00]** That's not true with the copy editor skill, right? It's fine that it changed, and I just said, fine, just check it for grammar; I'll check it for everything else. Or I'll ask an actual human being to check it for everything else, which is what I should be doing anyway.

**[00:00:00]** So there you go. The difference between AI and automation, or what I'm calling interpretive automation versus deterministic automation, and how to figure out which one you should use. I'm gonna be talking about this a lot. My friend kind of put this as talking about conscientious AI usage, which I love. So if you wanna hear more of my thoughts on this, you should go over to streamlined.fm/join to join my newsletter. You'll be the first one to get my thoughts around conscientious AI usage. Again, that's at streamlined.fm/join.

**[00:00:00]** That's it for this episode of the Streamlined Solopreneur. I would love to hear what you think over at streamlinedfeedback.com.

**[00:00:00]** Thanks so much for listening, and until next time. I hope you find some space in your week.
