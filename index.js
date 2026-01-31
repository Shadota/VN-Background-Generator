/* eslint-disable no-undef */
import { extension_settings, getContext } from "../../../extensions.js";
import { saveSettingsDebounced, eventSource, event_types, getRequestHeaders } from "../../../../script.js";

const extensionName = "Image-gen-kazuma";
const extensionFolderPath = `scripts/extensions/third-party/${extensionName}`;

// === HARDCODED GENERATION PARAMETERS (Illustrious XL optimized) ===
const HARDCODED_PARAMS = {
    steps: 24,
    cfg: 5.5,
    sampler_name: "euler_ancestral",
    scheduler: "normal",
    width: 1216,
    height: 832,
    denoise: 1.0,
    clip_skip: -1,  // CLIP skip 1
    batch_size: 1
};

// === HARDCODED NEGATIVE PROMPT ===
const HARDCODED_NEGATIVE = "lowres, bad anatomy, bad hands, text, error, worst quality, low quality, jpeg artifacts, watermark, signature, username, scan, displeasing, oldest, early, chromatic aberration, artistic error, unfinished, 1girl, 1boy, 1other, person, people, human, character, face, body, figure, solo";

// === ILLUSTRIOUS QUALITY TAGS ===
const ILLUSTRIOUS_QUALITY_TAGS = "masterpiece, absurdres, newest, best quality";

// === HARDCODED COMFYUI WORKFLOW (API format) ===
// Node structure: CheckpointLoader → CLIPSetLastLayer → [LoRA Chain] → CLIPTextEncode → KSampler → VAEDecode → SaveImage
// Workflow structure matching Dev-3 node IDs
const HARDCODED_WORKFLOW = {
    "4": {
        "class_type": "CheckpointLoaderSimple",
        "inputs": {
            "ckpt_name": "{{MODEL}}"
        }
    },
    "35": {
        "class_type": "LoraLoader",
        "inputs": {
            "model": ["4", 0],
            "clip": ["4", 1],
            "lora_name": "{{LORA1}}",
            "strength_model": 1.0,
            "strength_clip": 1.0
        }
    },
    "6": {
        "class_type": "CLIPTextEncode",
        "inputs": {
            "clip": ["35", 1],
            "text": "{{POSITIVE}}"
        }
    },
    "7": {
        "class_type": "CLIPTextEncode",
        "inputs": {
            "clip": ["35", 1],
            "text": "{{NEGATIVE}}"
        }
    },
    "5": {
        "class_type": "EmptyLatentImage",
        "inputs": {
            "width": 1344,
            "height": 768,
            "batch_size": 1
        }
    },
    "3": {
        "class_type": "KSampler",
        "inputs": {
            "model": ["35", 0],
            "positive": ["6", 0],
            "negative": ["7", 0],
            "latent_image": ["5", 0],
            "seed": -1,
            "steps": 24,
            "cfg": 5.5,
            "sampler_name": "euler_ancestral",
            "scheduler": "normal",
            "denoise": 1.0
        }
    },
    "8": {
        "class_type": "VAEDecode",
        "inputs": {
            "vae": ["4", 2],
            "samples": ["3", 0]
        }
    },
    "14": {
        "class_type": "SaveImage",
        "inputs": {
            "images": ["8", 0],
            "filename_prefix": "vnbg"
        }
    }
};

// === MINIMAL USER-CONFIGURABLE SETTINGS ===
const defaultSettings = {
    enabled: true,
    autoGenEnabled: false,
    comfyUrl: "http://127.0.0.1:8188",
    selectedModel: "",
    selectedLora: "",
    selectedLora2: "",
    selectedLora3: "",
    selectedLora4: "",
    selectedLoraWt: 1.0,
    selectedLoraWt2: 1.0,
    selectedLoraWt3: 1.0,
    selectedLoraWt4: 1.0,
    tagApiEndpoint: "",
    tagApiKey: "",
    tagModel: ""
};

// === SCENE EXTRACTION CONFIG ===
const SCENE_SYSTEM_PROMPT = `You extract scene settings from roleplay conversations as structured JSON for anime background image generation.

Output ONLY valid JSON with these fields:
{
  "location": "specific place as a danbooru tag (e.g. bedroom, forest, classroom, rooftop, city_street, cafe)",
  "time_of_day": "one of: morning, day, afternoon, evening, night, dawn, dusk",
  "weather": "one of: clear, cloudy, rain, snow, fog, storm, wind, none",
  "mood": "lighting and atmosphere as comma-separated tags (e.g. warm_ambient_lighting, soft_shadows, volumetric_lighting)",
  "key_elements": "notable background objects/architecture as comma-separated tags (e.g. bookshelf, marble_floor, ornate_furniture, tall_windows)"
}

RULES:
- Use the MOST RECENT scene description in the conversation
- If a location change happened, use the NEW location
- Use underscores for multi-word tags
- Prefer specific booru/danbooru tags over vague descriptions
- "mood" should describe LIGHTING and ATMOSPHERE, not emotions
- "key_elements" should describe ARCHITECTURAL details, MATERIALS, FURNITURE, and NATURAL elements
- Include material descriptions in key_elements (marble, wood, glass, stone, etc.)
- Do NOT include character descriptions — only the environment

EXAMPLES:
1. *They walk into the dimly lit library, rain pattering against tall windows*
{"location":"library","time_of_day":"evening","weather":"rain","mood":"dim_lighting, warm_ambient_lighting, soft_shadows","key_elements":"bookshelf, tall_windows, rain, wooden_floor, chandelier"}

2. *The morning sun bathes the rooftop in golden light as cherry blossoms drift by*
{"location":"rooftop","time_of_day":"morning","weather":"clear","mood":"golden_hour, cinematic_lighting, volumetric_lighting, atmospheric_haze","key_elements":"cherry_blossoms, railing, blue_sky, cityscape, fence"}

3. *She enters the grand ballroom, marble floors reflecting crystal chandeliers*
{"location":"ballroom","time_of_day":"evening","weather":"none","mood":"warm_ambient_lighting, professional_lighting, soft_shadows, volumetric_lighting","key_elements":"marble_floor, crystal_chandeliers, ornate_furniture, decorative_columns, tall_windows"}`;

const SCENE_TAG_GEN_CONFIG = {
    temperature: 0.15,
    top_p: 0.9,
    frequency_penalty: 0,
    presence_penalty: 0,
    max_tokens: 300,
    systemPrompt: SCENE_SYSTEM_PROMPT,
    assistantPrefill: '{"'
};

// === HELPER FUNCTIONS ===

function showKazumaProgress(text = "Processing...") {
    $("#kazuma_progress_text").text(text);
    $("#kazuma_progress_overlay").css("display", "flex");
}

function hideKazumaProgress() {
    $("#kazuma_progress_overlay").hide();
}

function blobToBase64(blob) {
    return new Promise((resolve) => {
        const reader = new FileReader();
        reader.onloadend = () => resolve(reader.result);
        reader.readAsDataURL(blob);
    });
}

function compressImage(base64Str, format = 'jpeg', quality = 0.9) {
    return new Promise((resolve) => {
        const img = new Image();
        img.src = base64Str;
        img.onload = () => {
            const canvas = document.createElement('canvas');
            canvas.width = img.width;
            canvas.height = img.height;
            const ctx = canvas.getContext('2d');
            ctx.drawImage(img, 0, 0);
            resolve(canvas.toDataURL(`image/${format}`, quality));
        };
        img.onerror = () => resolve(base64Str);
    });
}

// === WORKFLOW BUILDER ===

function buildWorkflowPrompt(positivePrompt) {
    const s = extension_settings[extensionName];
    const workflow = JSON.parse(JSON.stringify(HARDCODED_WORKFLOW));

    // Inject model (node 4 = CheckpointLoaderSimple)
    workflow["4"].inputs.ckpt_name = s.selectedModel;

    // LoRA configuration
    if (s.selectedLora && s.selectedLora !== "" && s.selectedLora !== "None") {
        // Use LoRA
        workflow["35"].inputs.lora_name = s.selectedLora;
        workflow["35"].inputs.strength_model = s.selectedLoraWt || 1.0;
        workflow["35"].inputs.strength_clip = s.selectedLoraWt || 1.0;
    } else {
        // No LoRA - remove node 35 and rewire to use checkpoint directly
        delete workflow["35"];
        workflow["6"].inputs.clip = ["4", 1];  // CLIP from checkpoint
        workflow["7"].inputs.clip = ["4", 1];  // CLIP from checkpoint
        workflow["3"].inputs.model = ["4", 0]; // Model from checkpoint
    }

    // Inject prompts (node 6 = positive, node 7 = negative)
    workflow["6"].inputs.text = positivePrompt;
    workflow["7"].inputs.text = HARDCODED_NEGATIVE;

    // Random seed (node 3 = KSampler)
    workflow["3"].inputs.seed = Math.floor(Math.random() * 2147483647);

    return workflow;
}

// === SCENE EXTRACTION ===

function validateAndRepairSceneState(sceneJson) {
    const VALID_TIMES = ['morning', 'day', 'afternoon', 'evening', 'night', 'dawn', 'dusk'];
    const VALID_WEATHER = ['clear', 'cloudy', 'rain', 'snow', 'fog', 'storm', 'wind', 'none'];

    if (!sceneJson.location || typeof sceneJson.location !== 'string') {
        sceneJson.location = 'indoors';
    }
    if (!sceneJson.time_of_day || !VALID_TIMES.includes(sceneJson.time_of_day)) {
        sceneJson.time_of_day = 'day';
    }
    if (!sceneJson.weather || !VALID_WEATHER.includes(sceneJson.weather)) {
        sceneJson.weather = 'clear';
    }
    if (sceneJson.mood && typeof sceneJson.mood !== 'string') {
        sceneJson.mood = '';
    }
    if (sceneJson.key_elements && typeof sceneJson.key_elements !== 'string') {
        sceneJson.key_elements = '';
    }

    return sceneJson;
}

function buildBackgroundPrompt(sceneJson) {
    const parts = [];

    // Environment base tags
    parts.push('no_humans', 'scenery', 'detailed_environment');

    // Composition tags for proper VN background framing
    parts.push('eye_level', 'centered_composition', 'depth_of_field', 'wide_shot');

    // Location
    const location = sceneJson.location.toLowerCase().replace(/\s+/g, '_');
    parts.push(location);

    // Key elements (architectural/natural)
    if (sceneJson.key_elements) {
        sceneJson.key_elements.split(',').map(t => t.trim().replace(/\s+/g, '_'))
            .filter(t => t).forEach(t => parts.push(t));
    }

    // Time of day mappings
    const TIME_MAPPINGS = {
        'morning': ['morning', 'sunlight', 'blue_sky'],
        'day': ['day', 'blue_sky', 'sunlight'],
        'afternoon': ['afternoon', 'sunlight', 'warm_lighting'],
        'evening': ['evening', 'orange_sky', 'sunset', 'warm_ambient_lighting'],
        'night': ['night', 'night_sky', 'moonlight', 'dark'],
        'dawn': ['dawn', 'sunrise', 'gradient_sky', 'atmospheric_haze'],
        'dusk': ['dusk', 'twilight', 'purple_sky', 'soft_shadows']
    };
    parts.push(...(TIME_MAPPINGS[sceneJson.time_of_day] || ['day']));

    // Weather mappings
    const WEATHER_MAPPINGS = {
        'clear': ['clear_sky'],
        'cloudy': ['cloudy', 'overcast'],
        'rain': ['rain', 'wet', 'puddle'],
        'snow': ['snowing', 'snow'],
        'fog': ['fog', 'mist', 'atmospheric_haze'],
        'storm': ['storm', 'lightning', 'dark_clouds', 'dramatic_lighting'],
        'wind': ['wind', 'dynamic_clouds'],
        'none': []
    };
    parts.push(...(WEATHER_MAPPINGS[sceneJson.weather] || []));

    // Mood/lighting from LLM
    if (sceneJson.mood) {
        sceneJson.mood.split(',').map(t => t.trim().replace(/\s+/g, '_'))
            .filter(t => t).forEach(t => parts.push(t));
    }

    // Quality tags (Illustrious)
    parts.push(...ILLUSTRIOUS_QUALITY_TAGS.split(', '));

    // Dedupe and join
    return parts.filter((t, i, arr) => arr.indexOf(t) === i).join(', ');
}

async function generateScenePrompt(sceneText) {
    const s = extension_settings[extensionName];

    if (!s.tagApiEndpoint || !s.tagModel) {
        throw new Error("Scene Extraction API not configured. Please set endpoint and model.");
    }

    const messages = [
        { role: 'system', content: SCENE_TAG_GEN_CONFIG.systemPrompt },
        { role: 'user', content: sceneText }
    ];

    if (SCENE_TAG_GEN_CONFIG.assistantPrefill) {
        messages.push({ role: 'assistant', content: SCENE_TAG_GEN_CONFIG.assistantPrefill });
    }

    const requestBody = {
        model: s.tagModel,
        messages: messages,
        max_tokens: SCENE_TAG_GEN_CONFIG.max_tokens,
        temperature: SCENE_TAG_GEN_CONFIG.temperature,
        top_p: SCENE_TAG_GEN_CONFIG.top_p,
        frequency_penalty: SCENE_TAG_GEN_CONFIG.frequency_penalty,
        presence_penalty: SCENE_TAG_GEN_CONFIG.presence_penalty
    };

    const headers = { 'Content-Type': 'application/json' };
    if (s.tagApiKey) {
        headers['Authorization'] = `Bearer ${s.tagApiKey}`;
    }

    const response = await fetch(s.tagApiEndpoint, {
        method: 'POST',
        headers: headers,
        body: JSON.stringify(requestBody)
    });

    if (!response.ok) {
        const error = await response.text();
        throw new Error(`Scene API request failed (${response.status}): ${error}`);
    }

    const data = await response.json();
    let result = data.choices[0].message.content;

    // Strip thinking tags
    if (result.includes('</think>')) {
        result = result.split('</think>').pop().trim();
    }
    result = result.replace(/<think>[\s\S]*?<\/think>/gi, '').trim();
    result = result.replace(/<\/?think>/gi, '').trim();

    // Prepend assistant prefill if needed
    if (SCENE_TAG_GEN_CONFIG.assistantPrefill && !result.trim().startsWith('{')) {
        result = SCENE_TAG_GEN_CONFIG.assistantPrefill + result;
    }

    // Extract JSON
    let jsonStr = result;
    const jsonMatch = result.match(/```(?:json)?\s*([\s\S]*?)```/);
    if (jsonMatch) {
        jsonStr = jsonMatch[1].trim();
    } else {
        const objMatch = result.match(/\{[\s\S]*?\}/);
        if (objMatch) jsonStr = objMatch[0];
    }

    let sceneJson;
    try {
        sceneJson = JSON.parse(jsonStr);
    } catch (e) {
        console.error(`[${extensionName}] Failed to parse scene JSON: ${jsonStr}`);
        sceneJson = { location: 'indoors', time_of_day: 'day', weather: 'clear', mood: '', key_elements: '' };
    }

    sceneJson = validateAndRepairSceneState(sceneJson);
    console.log(`[${extensionName}] Extracted scene:`, sceneJson);

    const prompt = buildBackgroundPrompt(sceneJson);
    console.log(`[${extensionName}] Generated prompt: ${prompt}`);

    return prompt;
}

// === BACKGROUND GENERATION ===

async function onGeneratePrompt() {
    if (!extension_settings[extensionName].enabled) return;
    if (isGenerating) return;

    const context = getContext();
    if (!context.chat || context.chat.length === 0) {
        toastr.warning("No chat history.");
        return;
    }

    const s = extension_settings[extensionName];

    if (!s.tagApiEndpoint || !s.tagModel) {
        toastr.error("Scene Extraction API not configured. Please set endpoint and model.");
        return;
    }

    if (!s.selectedModel) {
        toastr.error("No checkpoint selected. Please select a model in the extension settings.");
        return;
    }

    // Validate model exists in dropdown (helps catch stale selections)
    const modelExists = $("#kazuma_model_list option").filter((_, el) => el.value === s.selectedModel).length > 0;
    if (!modelExists) {
        console.warn(`[${extensionName}] Selected model "${s.selectedModel}" not found in dropdown. Refreshing lists...`);
        await fetchComfyLists();
    }

    isGenerating = true;
    showKazumaProgress("Checking ComfyUI...");

    // Check if ComfyUI is ready
    const comfyReady = await checkComfyUIReady();
    if (!comfyReady) {
        hideKazumaProgress();
        isGenerating = false;
        toastr.warning("ComfyUI is still loading models. Please wait a moment and try again.");
        return;
    }

    showKazumaProgress("Extracting Scene...");

    try {
        const NUM_CONTEXT_MESSAGES = 5;
        const recentMessages = context.chat.slice(-NUM_CONTEXT_MESSAGES)
            .map(msg => `${msg.is_user ? 'User' : 'Character'}: ${msg.mes}`)
            .join('\n\n');

        const sceneText = `Analyze the conversation below. Determine the CURRENT SCENE/SETTING where the action is taking place.\n\n${recentMessages}`;

        const generatedText = await generateScenePrompt(sceneText);

        showKazumaProgress("Sending to ComfyUI...");
        await generateWithComfy(generatedText);

    } catch (err) {
        hideKazumaProgress();
        console.error(err);
        toastr.error(`Generation failed: ${err.message}`);
    } finally {
        isGenerating = false;
    }
}

async function generateWithComfy(positivePrompt) {
    const comfyUrl = extension_settings[extensionName].comfyUrl;

    // Build workflow with injected parameters
    const workflow = buildWorkflowPrompt(positivePrompt);

    console.log(`[${extensionName}] Sending workflow to ComfyUI`);

    try {
        // Direct connection to ComfyUI
        const res = await fetch(`${comfyUrl}/prompt`, {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ prompt: workflow })
        });
        const data = await res.json();
        console.log(`[${extensionName}] ComfyUI response:`, data);

        // Log node_errors first for debugging
        if (data.node_errors && Object.keys(data.node_errors).length > 0) {
            console.error(`[${extensionName}] Node errors detail:`, JSON.stringify(data.node_errors, null, 2));
        }

        // Check for validation errors in response
        if (data.error) {
            console.error(`[${extensionName}] ComfyUI error:`, data.error);
            const fullDetails = JSON.stringify(data);

            if (fullDetails.includes('not in []') || fullDetails.includes('Value not in list')) {
                throw new Error("ComfyUI hasn't finished loading models. Please wait a moment and try again, or refresh ComfyUI.");
            }
            const errorMsg = typeof data.error === 'string' ? data.error :
                             (data.error.message || JSON.stringify(data.error));
            throw new Error(errorMsg);
        }

        if (!data.prompt_id) {
            console.error(`[${extensionName}] No prompt_id in response:`, data);
            throw new Error("ComfyUI rejected the workflow - check browser console for details");
        }

        await waitForGeneration(comfyUrl, data.prompt_id, positivePrompt);
    } catch (e) {
        hideKazumaProgress();
        toastr.error("ComfyUI Error: " + e.message);
        console.error(`[${extensionName}] Full error:`, e);
    }
}

async function waitForGeneration(baseUrl, promptId, positivePrompt) {
    showKazumaProgress("Rendering Image...");

    const checkInterval = setInterval(async () => {
        try {
            const h = await (await fetch(`${baseUrl}/history/${promptId}`)).json();
            if (h[promptId]) {
                clearInterval(checkInterval);
                const outputs = h[promptId].outputs;
                let finalImage = null;

                for (const nodeId in outputs) {
                    const nodeOutput = outputs[nodeId];
                    if (nodeOutput.images && nodeOutput.images.length > 0) {
                        finalImage = nodeOutput.images[0];
                        break;
                    }
                }

                if (finalImage) {
                    showKazumaProgress("Setting Background...");
                    const imgUrl = `${baseUrl}/view?filename=${finalImage.filename}&subfolder=${finalImage.subfolder}&type=${finalImage.type}`;
                    await insertImageToChat(imgUrl);
                    hideKazumaProgress();
                } else {
                    hideKazumaProgress();
                    toastr.warning("No image output found");
                }
            }
        } catch (e) {
            // Keep polling
        }
    }, 1000);
}

// === SAVE AS BACKGROUND (Simplified) ===

async function saveAsBackground(base64FullURL) {
    try {
        const fetchRes = await fetch(base64FullURL);
        const blob = await fetchRes.blob();
        const timestamp = new Date().toISOString().replace(/[:.]/g, '-').slice(0, 19);
        const filename = `vnbg_${timestamp}.jpg`;

        const formData = new FormData();
        formData.set('avatar', blob, filename);

        const uploadRes = await fetch('/api/backgrounds/upload', {
            method: 'POST',
            headers: getRequestHeaders({ omitContentType: true }),
            body: formData,
            cache: 'no-cache',
        });

        if (!uploadRes.ok) throw new Error('Background upload failed');
        const bgName = await uploadRes.text();

        // Set as active background
        $('#bg1').css('background-image', `url("backgrounds/${encodeURIComponent(bgName)}")`);
    } catch (err) {
        console.error(`[${extensionName}] saveAsBackground failed:`, err);
        toastr.error(`Failed to set background: ${err.message}`);
    }
}

async function insertImageToChat(imgUrl) {
    try {
        const response = await fetch(imgUrl);
        const blob = await response.blob();
        let base64FullURL = await blobToBase64(blob);

        // Always compress to JPEG 0.9
        base64FullURL = await compressImage(base64FullURL, 'jpeg', 0.9);

        // Always save as background
        await saveAsBackground(base64FullURL);

    } catch (err) {
        console.error(err);
        toastr.error("Failed to process image.");
    }
}

// === COMFYUI CONNECTION ===

async function checkComfyUIReady() {
    const comfyUrl = extension_settings[extensionName].comfyUrl;
    try {
        // Check if ComfyUI has loaded its models by fetching object_info
        const res = await fetch(`${comfyUrl}/object_info/CheckpointLoaderSimple`);
        if (!res.ok) return false;

        const data = await res.json();
        const checkpoints = data?.CheckpointLoaderSimple?.input?.required?.ckpt_name?.[0];

        if (!checkpoints || checkpoints.length === 0) {
            console.warn(`[${extensionName}] ComfyUI model list is empty - still loading`);
            return false;
        }

        console.log(`[${extensionName}] ComfyUI ready with ${checkpoints.length} models`);
        return true;
    } catch (e) {
        console.warn(`[${extensionName}] ComfyUI not ready:`, e.message);
        return false;
    }
}

async function onTestConnection() {
    const url = extension_settings[extensionName].comfyUrl;
    try {
        const result = await fetch('/api/sd/comfy/ping', {
            method: 'POST',
            headers: getRequestHeaders(),
            body: JSON.stringify({ url: url })
        });
        if (result.ok) {
            console.log(`[${extensionName}] ComfyUI API connected`);
            await fetchComfyLists();
        } else {
            throw new Error('ComfyUI returned an error via proxy.');
        }
    } catch (error) {
        toastr.error(`Connection failed: ${error.message}`, "VN Background Gen");
    }
}

async function fetchComfyLists() {
    const comfyUrl = extension_settings[extensionName].comfyUrl;
    const modelSel = $("#kazuma_model_list");
    const loraSelectors = [
        $("#kazuma_lora_list"),
        $("#kazuma_lora_list_2"),
        $("#kazuma_lora_list_3"),
        $("#kazuma_lora_list_4")
    ];

    try {
        // Fetch models
        const modelRes = await fetch('/api/sd/comfy/models', {
            method: 'POST',
            headers: getRequestHeaders(),
            body: JSON.stringify({ url: comfyUrl })
        });

        if (modelRes.ok) {
            const models = await modelRes.json();
            modelSel.empty().append('<option value="">-- Select Model --</option>');
            models.forEach(m => {
                let val = (typeof m === 'object' && m !== null) ? m.value : m;
                let text = (typeof m === 'object' && m !== null && m.text) ? m.text : val;
                modelSel.append(`<option value="${val}">${text}</option>`);
            });
            if (extension_settings[extensionName].selectedModel) {
                modelSel.val(extension_settings[extensionName].selectedModel);
            }
        }

        // Fetch LoRAs
        const loraRes = await fetch(`${comfyUrl}/object_info/LoraLoader`);
        if (loraRes.ok) {
            const json = await loraRes.json();
            const files = json['LoraLoader'].input.required.lora_name[0];
            loraSelectors.forEach((sel, i) => {
                const k = i === 0 ? "selectedLora" : `selectedLora${i + 1}`;
                const v = extension_settings[extensionName][k];
                sel.empty().append('<option value="">-- No LoRA --</option>');
                files.forEach(f => sel.append(`<option value="${f}">${f}</option>`));
                if (v) sel.val(v);
            });
        }
    } catch (e) {
        console.warn(`[${extensionName}] Failed to fetch lists.`, e);
    }
}

// === MESSAGE HANDLER (Auto-generate on every AI message) ===

let isGenerating = false;
let lastGenerationTime = 0;
const GENERATION_COOLDOWN = 5000; // 5 second cooldown between generations

function onMessageReceived(id) {
    const s = extension_settings[extensionName];
    if (!s?.enabled) return;
    if (!s?.autoGenEnabled) return; // Skip if auto-generation is disabled

    const chat = getContext().chat;
    if (!chat || !chat.length) return;

    const lastMsg = chat[chat.length - 1];
    // Only trigger on AI messages (not user, not system)
    if (lastMsg.is_user || lastMsg.is_system) return;

    // Prevent concurrent generations
    if (isGenerating) {
        console.log(`[${extensionName}] Skipping - generation already in progress`);
        return;
    }

    // Enforce cooldown
    const now = Date.now();
    if (now - lastGenerationTime < GENERATION_COOLDOWN) {
        console.log(`[${extensionName}] Skipping - cooldown active`);
        return;
    }

    console.log(`[${extensionName}] Auto-generating background...`);
    lastGenerationTime = now;
    setTimeout(onGeneratePrompt, 500);
}

// === SETTINGS MANAGEMENT ===

async function loadSettings() {
    if (!extension_settings[extensionName]) {
        extension_settings[extensionName] = {};
    }

    for (const key in defaultSettings) {
        if (typeof extension_settings[extensionName][key] === 'undefined') {
            extension_settings[extensionName][key] = defaultSettings[key];
        }
    }

    const s = extension_settings[extensionName];

    $("#kazuma_enable").prop("checked", s.enabled);
    $("#kazuma_auto_gen").prop("checked", s.autoGenEnabled);
    $("#kazuma_url").val(s.comfyUrl);
    $("#kazuma_tag_endpoint").val(s.tagApiEndpoint || "");
    $("#kazuma_tag_api_key").val(s.tagApiKey || "");
    $("#kazuma_tag_model").val(s.tagModel || "");

    // LoRA weights
    $("#kazuma_lora_wt").val(s.selectedLoraWt);
    $("#kazuma_lora_wt_display").text(s.selectedLoraWt);
    $("#kazuma_lora_wt_2").val(s.selectedLoraWt2);
    $("#kazuma_lora_wt_display_2").text(s.selectedLoraWt2);
    $("#kazuma_lora_wt_3").val(s.selectedLoraWt3);
    $("#kazuma_lora_wt_display_3").text(s.selectedLoraWt3);
    $("#kazuma_lora_wt_4").val(s.selectedLoraWt4);
    $("#kazuma_lora_wt_display_4").text(s.selectedLoraWt4);

    await fetchComfyLists();
}

// === INITIALIZATION ===

jQuery(async () => {
    try {
        // Inject progress bar HTML
        if ($("#kazuma_progress_overlay").length === 0) {
            $("body").append(`
                <div id="kazuma_progress_overlay">
                    <div style="flex:1">
                        <span id="kazuma_progress_text">Generating Image...</span>
                        <div class="kazuma-bar-container">
                            <div class="kazuma-bar-fill"></div>
                        </div>
                    </div>
                </div>
            `);
        }

        // Load HTML template
        await $.get(`${extensionFolderPath}/example.html`).then(h => $("#extensions_settings2").append(h));

        // Add standalone regenerate background button near send button
        const addRegenButton = () => {
            if ($("#kazuma_regen_btn").length > 0) return; // Already added

            const $sendForm = $("#send_form");
            const $rightSendForm = $("#rightSendForm");

            if ($rightSendForm.length > 0) {
                // Create button matching SillyTavern's style
                const regenBtn = $(`
                    <div id="kazuma_regen_btn" class="fa-solid fa-panorama interactable"
                         tabindex="0" title="Generate VN Background"
                         data-i18n="[title]Generate VN Background"></div>
                `);

                regenBtn.on("click", () => {
                    if (!extension_settings[extensionName].enabled) {
                        toastr.warning("VN Background Gen is disabled");
                        return;
                    }
                    console.log(`[${extensionName}] Manual background generation triggered`);
                    onGeneratePrompt();
                });

                // Prepend to right side (before send button)
                $rightSendForm.prepend(regenBtn);
                console.log(`[${extensionName}] Regen button added to rightSendForm`);
            }
        };

        // Try immediately and also observe for DOM changes
        addRegenButton();
        const observer = new MutationObserver(() => addRegenButton());
        observer.observe(document.body, { childList: true, subtree: true });

        // Stop observing after 10 seconds
        setTimeout(() => observer.disconnect(), 10000);

        // Bind event handlers
        $("#kazuma_enable").on("change", (e) => {
            extension_settings[extensionName].enabled = $(e.target).prop("checked");
            saveSettingsDebounced();
        });

        $("#kazuma_auto_gen").on("change", (e) => {
            extension_settings[extensionName].autoGenEnabled = $(e.target).prop("checked");
            saveSettingsDebounced();
        });

        $("#kazuma_url").on("input", (e) => {
            extension_settings[extensionName].comfyUrl = $(e.target).val();
            saveSettingsDebounced();
        });

        $("#kazuma_tag_endpoint").on("input", (e) => {
            extension_settings[extensionName].tagApiEndpoint = $(e.target).val();
            saveSettingsDebounced();
        });

        $("#kazuma_tag_api_key").on("input", (e) => {
            extension_settings[extensionName].tagApiKey = $(e.target).val();
            saveSettingsDebounced();
        });

        $("#kazuma_tag_model").on("input", (e) => {
            extension_settings[extensionName].tagModel = $(e.target).val();
            saveSettingsDebounced();
        });

        $("#kazuma_test_btn").on("click", onTestConnection);

        $("#kazuma_model_list").on("change", (e) => {
            extension_settings[extensionName].selectedModel = $(e.target).val();
            saveSettingsDebounced();
        });

        // LoRA dropdowns
        $("#kazuma_lora_list").on("change", (e) => {
            extension_settings[extensionName].selectedLora = $(e.target).val();
            saveSettingsDebounced();
        });
        $("#kazuma_lora_list_2").on("change", (e) => {
            extension_settings[extensionName].selectedLora2 = $(e.target).val();
            saveSettingsDebounced();
        });
        $("#kazuma_lora_list_3").on("change", (e) => {
            extension_settings[extensionName].selectedLora3 = $(e.target).val();
            saveSettingsDebounced();
        });
        $("#kazuma_lora_list_4").on("change", (e) => {
            extension_settings[extensionName].selectedLora4 = $(e.target).val();
            saveSettingsDebounced();
        });

        // LoRA weight sliders
        $("#kazuma_lora_wt").on("input", (e) => {
            let v = parseFloat($(e.target).val());
            extension_settings[extensionName].selectedLoraWt = v;
            $("#kazuma_lora_wt_display").text(v);
            saveSettingsDebounced();
        });
        $("#kazuma_lora_wt_2").on("input", (e) => {
            let v = parseFloat($(e.target).val());
            extension_settings[extensionName].selectedLoraWt2 = v;
            $("#kazuma_lora_wt_display_2").text(v);
            saveSettingsDebounced();
        });
        $("#kazuma_lora_wt_3").on("input", (e) => {
            let v = parseFloat($(e.target).val());
            extension_settings[extensionName].selectedLoraWt3 = v;
            $("#kazuma_lora_wt_display_3").text(v);
            saveSettingsDebounced();
        });
        $("#kazuma_lora_wt_4").on("input", (e) => {
            let v = parseFloat($(e.target).val());
            extension_settings[extensionName].selectedLoraWt4 = v;
            $("#kazuma_lora_wt_display_4").text(v);
            saveSettingsDebounced();
        });

        // Load settings
        loadSettings();

        // Register message handler for auto-generation
        eventSource.on(event_types.MESSAGE_RECEIVED, onMessageReceived);

    } catch (e) {
        console.error(`[${extensionName}] Initialization failed:`, e);
    }
});
