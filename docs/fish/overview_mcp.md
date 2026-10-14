> ## Documentation Index
> Fetch the complete documentation index at: https://docs.fish.audio/llms.txt
> Use this file to discover all available pages before exploring further.

# MCP Server

> Connect Claude, Cursor, or any MCP client to your Fish Audio account: search voices, generate speech, transcribe audio, and create images and videos

export const PromptCard = ({title, icon, prompt, note}) => {
  const [state, setState] = useState("idle");
  const timer = useRef(null);
  useEffect(() => () => clearTimeout(timer.current), []);
  const hints = {
    idle: "Copy",
    copied: "Copied",
    failed: "Copy failed"
  };
  const setup = "Use the Fish Audio MCP server for this (https://api.fish.audio/mcp, streamable HTTP with OAuth sign-in). If it is not connected yet, help me add it before you start.";
  const copyWithTextarea = text => {
    const area = document.createElement("textarea");
    area.value = text;
    area.setAttribute("readonly", "");
    area.style.position = "fixed";
    area.style.opacity = "0";
    document.body.appendChild(area);
    area.select();
    const ok = document.execCommand("copy");
    document.body.removeChild(area);
    if (!ok) throw new Error("copy command failed");
  };
  const writeClipboard = async text => {
    try {
      await navigator.clipboard.writeText(text);
    } catch {
      copyWithTextarea(text);
    }
  };
  const copy = async () => {
    try {
      await writeClipboard(`${prompt}\n\n${setup}`);
      setState("copied");
    } catch {
      setState("failed");
    }
    clearTimeout(timer.current);
    timer.current = setTimeout(() => setState("idle"), 2000);
  };
  const onKeyDown = event => {
    if (event.key === "Enter" || event.key === " ") {
      event.preventDefault();
      copy();
    }
  };
  return <div className="prompt-card" data-state={state} role="button" tabIndex={0} aria-label={`Copy prompt: ${title}`} onClick={copy} onKeyDown={onKeyDown}>
      <Card title={title} icon={icon}>
        “{prompt}”{note ? ` ${note}` : ""}
        <span className="prompt-card-hint" aria-live="polite">
          {hints[state]}
        </span>
      </Card>
    </div>;
};

The Fish Audio MCP server gives AI agents direct access to your Fish Audio account: they can browse the voice library, generate speech, transcribe audio, and generate or edit images and videos for you.

* **Endpoint**: `https://api.fish.audio/mcp` (streamable HTTP)
* **Authentication**: OAuth. Your MCP client opens a browser window, you sign in with your Fish Audio account, and choose the team the connection works in.
* **Billing**: usage draws from your plan's package credits, exactly like the [web app](https://fish.audio/app). It does not consume developer API credits. Image and video generation is quoted first, and the agent asks you to confirm the price before it generates.

## Connect

<Tabs>
  <Tab title="Claude Code">
    ```bash theme={null}
    claude mcp add --transport http fish-audio https://api.fish.audio/mcp
    ```

    Run `/mcp` inside Claude Code to sign in, then ask "Generate a short greeting with a warm English voice."
  </Tab>

  <Tab title="Claude.ai">
    Go to **Settings → Connectors → Add custom connector** and enter
    `https://api.fish.audio/mcp`. Claude walks you through the sign-in.
  </Tab>

  <Tab title="Cursor">
    Open the command palette (`Cmd/Ctrl+Shift+P`) → "Open MCP settings" → "Add custom MCP", and add:

    ```json theme={null}
    {
      "mcpServers": {
        "fish-audio": { "url": "https://api.fish.audio/mcp" }
      }
    }
    ```

    Cursor prompts you to sign in on first use.
  </Tab>

  <Tab title="Codex CLI">
    ```bash theme={null}
    codex mcp add fish-audio https://api.fish.audio/mcp
    codex mcp login fish-audio
    ```

    `codex mcp login` opens the browser sign-in. Verify with `codex mcp list`.
  </Tab>

  <Tab title="Windsurf">
    Go to `Settings → Cascade → MCP Servers → View raw config` (`~/.codeium/windsurf/mcp_config.json`) and add:

    ```json theme={null}
    {
      "mcpServers": {
        "fish-audio": { "url": "https://api.fish.audio/mcp" }
      }
    }
    ```
  </Tab>
</Tabs>

## Try it

Once connected, ask in plain language and the agent picks the right tools. Click a card to copy its prompt; the copied text also names the server, so the agent can help you connect it if you have not yet.

<CardGroup cols={2}>
  <PromptCard title="Narrate a script" icon="microphone" prompt="Find a calm English narration voice, read intro.md aloud, and give me the audio link." />

  <PromptCard title="Voice casting" icon="magnifying-glass" prompt="Show me the three most popular Japanese voices and play their samples." />

  <PromptCard title="Transcribe a recording" icon="waveform" prompt="Transcribe meeting.mp3 and summarize the action items." note="(the agent uploads the file, then transcribes it)" />

  <PromptCard title="Check spend" icon="wallet" prompt="How many Fish Audio credits do I have left?" />

  <PromptCard title="Generate an image" icon="image" prompt="Create a 16:9 watercolor image of a lighthouse at dawn. Show me the price first, then generate it." />

  <PromptCard title="Edit an image" icon="paintbrush" prompt="Upload portrait.png and replace the background with a warm sunset. Estimate first, then generate after I confirm." />

  <PromptCard title="Generate a video" icon="video" prompt="Make a short 16:9 video of waves rolling onto a black-sand beach at sunset. Quote the credits, then generate." />

  <PromptCard title="Animate an image" icon="film" prompt="Turn the image you just generated into a short video with a slow push-in, and give me the video URL and what was charged." />
</CardGroup>

In coding agents like Claude Code and Codex, tools compose with the shell: the agent can download generated audio, images, and videos with `curl`, upload local recordings for transcription or reference images for editing, or batch-generate a directory of scripts.

## Good to know

* Add audio tags in square brackets inside the text to control delivery: `[whispering]`, `[excited]`, `[laughing]`. Tags are performed, never spoken.
* If no voice is specified, a curated default voice for the requested language is used.
* Local files can be transcribed too. The agent uploads them to a temporary slot that is deleted automatically after 7 days.
* Before an image or video is generated, the agent requests a credit estimate and asks you to confirm it. The server re-checks the price when the job is submitted and never charges more than the amount you approved.
* Video generation needs a Plus plan or higher. Free plans have a daily image allowance and a smaller image count per request; the estimate reports these limits before you are asked to approve anything.
* Reference images for editing or image-to-video are JPEG, PNG, or WebP files up to 20 MB. The agent uploads them for you, and an image it just generated can be reused as input without downloading it.
* Generated audio, images, and videos are returned as permanent URLs; failed generations are refunded.
* A connection is bound to the team you chose at sign-in. To work in another team, add the server again and choose that team.


This documentation is built and hosted on [Mintlify](https://mintlify.com), a developer documentation platform.