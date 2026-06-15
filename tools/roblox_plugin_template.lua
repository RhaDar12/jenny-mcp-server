-- Jenny Roblox Studio Bridge Plugin
-- This configured file contains a local bridge token. Do not upload it.

local HttpService = game:GetService("HttpService")
local Selection = game:GetService("Selection")
local ChangeHistoryService = game:GetService("ChangeHistoryService")
local RunService = game:GetService("RunService")
local ScriptEditorService = game:GetService("ScriptEditorService")

local BRIDGE_URL = "__BRIDGE_URL__"
local BRIDGE_TOKEN = "__BRIDGE_TOKEN__"
local POLL_INTERVAL = 0.6
local PLUGIN_VERSION = "3.0.0-privileged-approval"

local toolbar = plugin:CreateToolbar("Jenny AI")
local toggleButton = toolbar:CreateButton(
    "JennyBridgeToggle",
    "Aktif/nonaktifkan Jenny Roblox Bridge",
    "",
    "Jenny Bridge"
)

local running = true
local unloaded = false
toggleButton:SetActive(true)

local function request(method, endpoint, body)
    local data = {
        Url = BRIDGE_URL .. endpoint,
        Method = method,
        Headers = {
            ["Content-Type"] = "application/json",
            ["Accept"] = "application/json",
            ["X-Jenny-Token"] = BRIDGE_TOKEN,
        },
    }

    if body ~= nil then
        data.Body = HttpService:JSONEncode(body)
    end

    local response = HttpService:RequestAsync(data)

    if not response.Success then
        error(
            string.format(
                "HTTP %s gagal (%s): %s",
                endpoint,
                tostring(response.StatusCode),
                tostring(response.Body)
            )
        )
    end

    if response.Body == nil or response.Body == "" then
        return {}
    end

    return HttpService:JSONDecode(response.Body)
end

local function splitPath(path)
    local parts = {}

    for part in string.gmatch(path or "", "[^/]+") do
        table.insert(parts, part)
    end

    return parts
end

local function resolvePath(path)
    if path == nil or path == "" or path == "game" then
        return game
    end

    local parts = splitPath(path)

    if #parts == 0 then
        return game
    end

    local current
    local ok, service = pcall(function()
        return game:GetService(parts[1])
    end)

    if ok then
        current = service
    else
        current = game:FindFirstChild(parts[1])
    end

    if current == nil then
        return nil
    end

    for index = 2, #parts do
        current = current:FindFirstChild(parts[index])

        if current == nil then
            return nil
        end
    end

    return current
end

local function instancePath(instance)
    if instance == game then
        return "game"
    end

    local parts = {}
    local current = instance

    while current ~= nil and current ~= game do
        table.insert(parts, 1, current.Name)
        current = current.Parent
    end

    return table.concat(parts, "/")
end

local function vector3ToTable(value)
    return {
        x = value.X,
        y = value.Y,
        z = value.Z,
    }
end

local function color3ToTable(value)
    return {
        r = math.round(value.R * 255),
        g = math.round(value.G * 255),
        b = math.round(value.B * 255),
    }
end

local function serializeInstance(instance)
    local output = {
        name = instance.Name,
        class_name = instance.ClassName,
        path = instancePath(instance),
        parent_path = instance.Parent and instancePath(instance.Parent) or nil,
        archivable = instance.Archivable,
    }

    if instance:IsA("BasePart") then
        output.position = vector3ToTable(instance.Position)
        output.orientation = vector3ToTable(instance.Orientation)
        output.size = vector3ToTable(instance.Size)
        output.color = color3ToTable(instance.Color)
        output.material = instance.Material.Name
        output.transparency = instance.Transparency
        output.anchored = instance.Anchored
        output.can_collide = instance.CanCollide
        output.can_touch = instance.CanTouch
        output.can_query = instance.CanQuery
    end

    return output
end

local function serializeTree(instance, depth, maxDepth, maxChildren)
    local node = serializeInstance(instance)
    node.children = {}

    if depth >= maxDepth then
        node.child_count = #instance:GetChildren()
        node.truncated = node.child_count > 0
        return node
    end

    local children = instance:GetChildren()

    table.sort(children, function(a, b)
        return string.lower(a.Name) < string.lower(b.Name)
    end)

    local limit = math.min(#children, maxChildren)

    for index = 1, limit do
        table.insert(
            node.children,
            serializeTree(
                children[index],
                depth + 1,
                maxDepth,
                maxChildren
            )
        )
    end

    node.child_count = #children
    node.truncated = #children > maxChildren

    return node
end

local function tableToVector3(value, fieldName)
    if type(value) ~= "table" then
        error(fieldName .. " harus berupa object {x,y,z}.")
    end

    return Vector3.new(
        tonumber(value.x) or 0,
        tonumber(value.y) or 0,
        tonumber(value.z) or 0
    )
end

local function tableToColor3(value)
    if type(value) ~= "table" then
        error("Color harus berupa object {r,g,b}.")
    end

    return Color3.fromRGB(
        math.clamp(tonumber(value.r) or 0, 0, 255),
        math.clamp(tonumber(value.g) or 0, 0, 255),
        math.clamp(tonumber(value.b) or 0, 0, 255)
    )
end

local function beginRecording(name)
    local identifier = ChangeHistoryService:TryBeginRecording(
        "Jenny_" .. name,
        "Jenny: " .. name
    )

    if identifier == nil then
        error(
            "Tidak dapat memulai undo recording. "
            .. "Pastikan Studio tidak sedang Play Test."
        )
    end

    return identifier
end

local function finishRecording(identifier, commit)
    ChangeHistoryService:FinishRecording(
        identifier,
        commit
            and Enum.FinishRecordingOperation.Commit
            or Enum.FinishRecordingOperation.Cancel
    )
end

local function withRecording(name, callback)
    local identifier = beginRecording(name)
    local ok, result = pcall(callback)

    if ok then
        finishRecording(identifier, true)
        return result
    end

    finishRecording(identifier, false)
    error(result)
end

local ALLOWED_PROPERTIES = {
    Name = true,
    Anchored = true,
    CanCollide = true,
    CanTouch = true,
    CanQuery = true,
    Transparency = true,
    Reflectance = true,
    CastShadow = true,
    Material = true,
    Color = true,
    Size = true,
    Position = true,
    Orientation = true,
}

local function setAllowedProperty(instance, propertyName, value)
    if not ALLOWED_PROPERTIES[propertyName] then
        error("Property tidak diizinkan: " .. tostring(propertyName))
    end

    if propertyName == "Color" then
        if not instance:IsA("BasePart") then
            error("Color hanya didukung untuk BasePart.")
        end
        instance.Color = tableToColor3(value)

    elseif propertyName == "Size" then
        if not instance:IsA("BasePart") then
            error("Size hanya didukung untuk BasePart.")
        end
        instance.Size = tableToVector3(value, "Size")

    elseif propertyName == "Position" then
        if not instance:IsA("BasePart") then
            error("Position hanya didukung untuk BasePart.")
        end
        instance.Position = tableToVector3(value, "Position")

    elseif propertyName == "Orientation" then
        if not instance:IsA("BasePart") then
            error("Orientation hanya didukung untuk BasePart.")
        end
        instance.Orientation = tableToVector3(value, "Orientation")

    elseif propertyName == "Material" then
        if not instance:IsA("BasePart") then
            error("Material hanya didukung untuk BasePart.")
        end

        local material = Enum.Material[tostring(value)]

        if material == nil then
            error("Material tidak valid: " .. tostring(value))
        end

        instance.Material = material

    else
        instance[propertyName] = value
    end
end


local function getBounds(instance)
    if instance:IsA("BasePart") then
        return instance.CFrame, instance.Size
    end

    if instance:IsA("Model") then
        local ok, boundsCFrame, boundsSize = pcall(function()
            return instance:GetBoundingBox()
        end)

        if ok then
            return boundsCFrame, boundsSize
        end
    end

    local parts = {}

    if instance:IsA("BasePart") then
        table.insert(parts, instance)
    end

    for _, descendant in ipairs(instance:GetDescendants()) do
        if descendant:IsA("BasePart") then
            table.insert(parts, descendant)
        end
    end

    if #parts == 0 then
        error(
            "Target tidak memiliki BasePart yang dapat difokuskan: "
            .. instancePath(instance)
        )
    end

    local minPoint = Vector3.new(
        math.huge,
        math.huge,
        math.huge
    )
    local maxPoint = Vector3.new(
        -math.huge,
        -math.huge,
        -math.huge
    )

    for _, part in ipairs(parts) do
        local half = part.Size * 0.5

        for x = -1, 1, 2 do
            for y = -1, 1, 2 do
                for z = -1, 1, 2 do
                    local corner = part.CFrame:PointToWorldSpace(
                        Vector3.new(
                            half.X * x,
                            half.Y * y,
                            half.Z * z
                        )
                    )

                    minPoint = Vector3.new(
                        math.min(minPoint.X, corner.X),
                        math.min(minPoint.Y, corner.Y),
                        math.min(minPoint.Z, corner.Z)
                    )
                    maxPoint = Vector3.new(
                        math.max(maxPoint.X, corner.X),
                        math.max(maxPoint.Y, corner.Y),
                        math.max(maxPoint.Z, corner.Z)
                    )
                end
            end
        end
    end

    local center = (minPoint + maxPoint) * 0.5
    local size = maxPoint - minPoint

    return CFrame.new(center), size
end

local VIEW_DIRECTIONS = {
    isometric = Vector3.new(1, 0.7, 1),
    front = Vector3.new(0, 0, 1),
    back = Vector3.new(0, 0, -1),
    left = Vector3.new(-1, 0, 0),
    right = Vector3.new(1, 0, 0),
    top = Vector3.new(0, 1, 0.001),
}

local function focusCamera(instance, viewName, padding)
    local camera = workspace.CurrentCamera

    if camera == nil then
        error("Workspace.CurrentCamera tidak tersedia.")
    end

    local boundsCFrame, boundsSize = getBounds(instance)
    local center = boundsCFrame.Position
    local view = tostring(viewName or "isometric")
    local safePadding = math.clamp(
        tonumber(padding) or 1.25,
        1,
        5
    )

    if view ~= "current" then
        local direction = VIEW_DIRECTIONS[view]

        if direction == nil then
            error("View tidak didukung: " .. view)
        end

        direction = direction.Unit

        local largest = math.max(
            boundsSize.X,
            boundsSize.Y,
            boundsSize.Z,
            1
        )
        local distance = largest * 4
        local up = Vector3.new(0, 1, 0)

        if view == "top" then
            up = Vector3.new(0, 0, -1)
        end

        camera.CFrame = CFrame.lookAt(
            center + direction * distance,
            center,
            up
        )
    end

    camera.Focus = CFrame.new(center)
    camera:ZoomToExtents(
        boundsCFrame,
        boundsSize * safePadding
    )

    return {
        target = serializeInstance(instance),
        view = view,
        padding = safePadding,
        bounds_center = vector3ToTable(boundsCFrame.Position),
        bounds_size = vector3ToTable(boundsSize),
        camera_position = vector3ToTable(camera.CFrame.Position),
        camera_focus = vector3ToTable(camera.Focus.Position),
    }
end

local function executeCommand(command)
    local action = command.action
    local payload = command.payload or {}

    if action == "ping" then
        return {
            pong = true,
            place_id = game.PlaceId,
            place_name = game.Name,
        }

    elseif action == "get_place_info" then
        return {
            place_id = game.PlaceId,
            game_id = game.GameId,
            place_name = game.Name,
            creator_id = game.CreatorId,
            creator_type = game.CreatorType.Name,
            is_playing = RunService:IsRunning(),
        }

    elseif action == "get_selection" then
        local items = {}

        for _, instance in ipairs(Selection:Get()) do
            table.insert(items, serializeInstance(instance))
        end

        return {
            count = #items,
            items = items,
        }

    elseif action == "get_hierarchy" then
        local root = resolvePath(payload.root or "Workspace")

        if root == nil then
            error("Root tidak ditemukan: " .. tostring(payload.root))
        end

        return {
            root = serializeTree(
                root,
                0,
                math.clamp(tonumber(payload.max_depth) or 3, 0, 8),
                math.clamp(tonumber(payload.max_children) or 100, 1, 500)
            ),
        }

    elseif action == "get_instance" then
        local instance = resolvePath(payload.path)

        if instance == nil then
            error("Instance tidak ditemukan: " .. tostring(payload.path))
        end

        local result = serializeInstance(instance)
        result.child_count = #instance:GetChildren()
        return result

    elseif action == "select_instance" then
        local instance = resolvePath(payload.path)

        if instance == nil then
            error("Instance tidak ditemukan: " .. tostring(payload.path))
        end

        Selection:Set({instance})

        return {
            selected = serializeInstance(instance),
        }


    elseif action == "visual_inspect_prepare" then
        local instance = resolvePath(payload.path)

        if instance == nil then
            error(
                "Instance tidak ditemukan: "
                .. tostring(payload.path)
            )
        end

        Selection:Set({instance})

        return focusCamera(
            instance,
            payload.view,
            payload.padding
        )

    elseif action == "visual_inspect_selection" then
        local selected = Selection:Get()

        if #selected == 0 then
            error("Tidak ada Instance yang dipilih di Studio.")
        end

        return focusCamera(
            selected[1],
            payload.view,
            payload.padding
        )

    elseif action == "create_part" then
        return withRecording("Create Part", function()
            local parent = resolvePath(payload.parent or "Workspace")

            if parent == nil then
                error("Parent tidak ditemukan: " .. tostring(payload.parent))
            end

            local part = Instance.new("Part")
            part.Name = tostring(payload.name or "JennyPart")
            part.Position = tableToVector3(
                payload.position or {x = 0, y = 5, z = 0},
                "position"
            )
            part.Size = tableToVector3(
                payload.size or {x = 4, y = 1, z = 4},
                "size"
            )
            part.Anchored = payload.anchored == true
            part.CanCollide = payload.can_collide ~= false
            part.Parent = parent
            Selection:Set({part})

            return {
                created = serializeInstance(part),
            }
        end)

    elseif action == "set_properties" then
        return withRecording("Set Properties", function()
            local instance = resolvePath(payload.path)

            if instance == nil then
                error("Instance tidak ditemukan: " .. tostring(payload.path))
            end

            if type(payload.properties) ~= "table" then
                error("properties harus berupa object.")
            end

            local changed = {}

            for propertyName, value in pairs(payload.properties) do
                setAllowedProperty(
                    instance,
                    tostring(propertyName),
                    value
                )
                changed[propertyName] = value
            end

            return {
                instance = serializeInstance(instance),
                changed = changed,
            }
        end)

    elseif action == "rename_instance" then
        return withRecording("Rename Instance", function()
            local instance = resolvePath(payload.path)
            local newName = tostring(payload.new_name or "")

            if instance == nil then
                error("Instance tidak ditemukan: " .. tostring(payload.path))
            end

            if newName == "" then
                error("new_name tidak boleh kosong.")
            end

            local oldPath = instancePath(instance)
            instance.Name = newName

            return {
                old_path = oldPath,
                instance = serializeInstance(instance),
            }
        end)


    elseif action == "delete_instance" then
        return withRecording("Delete Instance", function()
            local instance = resolvePath(payload.path)

            if instance == nil then
                error(
                    "Instance tidak ditemukan: "
                    .. tostring(payload.path)
                )
            end

            if instance == game or instance.Parent == game then
                error(
                    "game dan service root tidak boleh dihapus."
                )
            end

            if RunService:IsRunning() then
                error(
                    "Penghapusan dibatalkan karena Studio "
                    .. "sedang Play Test."
                )
            end

            local deleted = serializeInstance(instance)
            Selection:Set({})
            instance:Destroy()

            return {
                deleted = deleted,
                undo_available = true,
            }
        end)

    elseif action == "update_script_source" then
        return withRecording("Update Script Source", function()
            local instance = resolvePath(payload.path)

            if instance == nil then
                error(
                    "Script tidak ditemukan: "
                    .. tostring(payload.path)
                )
            end

            if not instance:IsA("LuaSourceContainer") then
                error(
                    "Target bukan Script, LocalScript, "
                    .. "atau ModuleScript."
                )
            end

            if RunService:IsRunning() then
                error(
                    "Edit Script dibatalkan karena Studio "
                    .. "sedang Play Test."
                )
            end

            local newSource = payload.source

            if type(newSource) ~= "string" then
                error("source harus berupa string.")
            end

            if #newSource > 500000 then
                error(
                    "Source terlalu besar. Batas maksimal "
                    .. "500.000 karakter."
                )
            end

            if string.find(newSource, "\0", 1, true) then
                error("Source tidak boleh mengandung null byte.")
            end

            local oldLength = 0

            ScriptEditorService:UpdateSourceAsync(
                instance,
                function(oldSource)
                    oldLength = #oldSource
                    return newSource
                end
            )

            return {
                script = serializeInstance(instance),
                old_source_length = oldLength,
                new_source_length = #newSource,
                undo_available = true,
            }
        end)

    elseif action == "reparent_instance" then
        return withRecording("Reparent Instance", function()
            local instance = resolvePath(payload.path)
            local newParent = resolvePath(payload.new_parent)

            if instance == nil then
                error("Instance tidak ditemukan: " .. tostring(payload.path))
            end

            if newParent == nil then
                error(
                    "Parent baru tidak ditemukan: "
                    .. tostring(payload.new_parent)
                )
            end

            if instance == game or instance.Parent == game then
                error("game dan service tidak boleh dipindahkan.")
            end

            instance.Parent = newParent

            return {
                instance = serializeInstance(instance),
            }
        end)

    else
        error("Action tidak didukung: " .. tostring(action))
    end
end

local function pluginInfo()
    return {
        place_id = game.PlaceId,
        game_id = game.GameId,
        place_name = game.Name,
        is_playing = RunService:IsRunning(),
        plugin_version = PLUGIN_VERSION,
    }
end

local function sendResult(commandId, success, result, errorMessage)
    request(
        "POST",
        "/v1/results/" .. commandId,
        {
            success = success,
            result = result,
            error = errorMessage,
            plugin_info = pluginInfo(),
        }
    )
end

local function processOneCommand()
    local response = request("GET", "/v1/commands/next", nil)
    local command = response.command

    if command == nil then
        return
    end

    local ok, result = pcall(executeCommand, command)

    local resultOk, resultError = pcall(function()
        if ok then
            sendResult(command.id, true, result, nil)
        else
            sendResult(command.id, false, nil, tostring(result))
        end
    end)

    if not resultOk then
        warn(
            "[Jenny Bridge] Gagal mengirim hasil: "
            .. tostring(resultError)
        )
    end
end

toggleButton.Click:Connect(function()
    running = not running
    toggleButton:SetActive(running)

    print(
        "[Jenny Bridge] "
        .. (running and "AKTIF" or "NONAKTIF")
    )
end)

plugin.Unloading:Connect(function()
    unloaded = true
    running = false
end)

task.spawn(function()
    print("[Jenny Bridge] Plugin aktif: " .. BRIDGE_URL)

    while not unloaded do
        if running then
            local ok, err = pcall(processOneCommand)

            if not ok then
                warn("[Jenny Bridge] " .. tostring(err))
            end
        end

        task.wait(POLL_INTERVAL)
    end
end)
