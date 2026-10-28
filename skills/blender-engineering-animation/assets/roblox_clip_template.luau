-- Roblox Studio local clip authoring template.
--
-- This module constructs an unparented KeyframeSequence from an explicitly
-- supplied rig and config. It does not publish, upload, search the cloud, or
-- discover a rig in Workspace. Registration and playback are opt-in and use
-- only an ID returned by the current AnimationClipProvider API. No working
-- asset ID is fabricated.
--
-- Scope: the KeyframeSequence/Pose route for a BasePart/Motor6D-compatible
-- hierarchy. Bone and AnimationConstraint targets require a CurveAnimation or
-- native import/editor adapter; this template rejects those route selections
-- instead of claiming that a legacy pose tree will retarget them.
--
-- Run registration/playback only in a disposable local preview target. Studio
-- MCP documents Edit, Client, and Server execution contexts, but the effective
-- Animation capability of this API in each context must be probed in the
-- current Studio build. This file performs no live probe by itself.
--
-- Minimal config shape (all pose samples are local joint CFrames):
-- {
--     name = "LocalClip",
--     fps = 30,
--     joints = {
--         {pose_name = "HumanoidRootPart", instance_name = "HumanoidRootPart", kind = "part_motor"},
--         {pose_name = "LowerTorso", instance_name = "LowerTorso", parent_pose = "HumanoidRootPart"},
--     },
--     poses = {
--         {time = 0, joints = {HumanoidRootPart = CFrame.new(), LowerTorso = CFrame.new()}},
--         {time = 0.5, joints = {HumanoidRootPart = CFrame.new(), LowerTorso = CFrame.Angles(0, 0.2, 0)}},
--     },
--     markers = {{keyframe = 2, name = "Impact", value = "cosmetic"}},
-- }

local RobloxClipTemplate = {}

RobloxClipTemplate.VERSION = "1.0.0"
RobloxClipTemplate.REPRESENTATION = "KeyframeSequence"

local OWNER_TOKEN = {}

local function is_instance(value)
	return typeof(value) == "Instance"
end

local function is_table(value)
	return type(value) == "table"
end

local function is_finite_number(value)
	return type(value) == "number"
		and value == value
		and value < math.huge
		and value > -math.huge
end

local function is_positive_integer(value)
	return type(value) == "number"
		and value == math.floor(value)
		and value >= 1
		and value < math.huge
end

local function add_error(errors, path, message)
	errors[#errors + 1] = path .. ": " .. message
end

local function is_nonempty_string(value)
	return type(value) == "string" and value:match("%S") ~= nil
end

local function is_finite_cframe(value)
	if typeof(value) ~= "CFrame" then
		return false
	end

	local components = { value:GetComponents() }
	for _, component in ipairs(components) do
		if not is_finite_number(component) then
			return false
		end
	end
	return true
end

local function is_array(value)
	if not is_table(value) then
		return false
	end

	local count = #value
	for key, _ in pairs(value) do
		if type(key) ~= "number"
			or key ~= math.floor(key)
			or key < 1
			or key > count then
			return false
		end
	end
	return true
end

local function get_target(rig, joint)
	local instance_name = joint.instance_name or joint.pose_name
	return rig:FindFirstChild(instance_name, true)
end

local function validate_joint_hierarchy(joints, errors)
	local by_pose_name = {}
	local root_count = 0

	for index, joint in ipairs(joints) do
		local path = string.format("config.joints[%d]", index)
		if not is_table(joint) then
			add_error(errors, path, "must be a table")
		else
			if not is_nonempty_string(joint.pose_name) then
				add_error(errors, path .. ".pose_name", "must be a non-empty string")
			elseif by_pose_name[joint.pose_name] then
				add_error(errors, path .. ".pose_name", "must be unique")
			else
				by_pose_name[joint.pose_name] = joint
			end
			if joint.instance_name ~= nil and not is_nonempty_string(joint.instance_name) then
				add_error(errors, path .. ".instance_name", "must be a non-empty string when provided")
			end

			if joint.parent_pose == nil or joint.parent_pose == "" then
				root_count += 1
			elseif type(joint.parent_pose) ~= "string" then
				add_error(errors, path .. ".parent_pose", "must be a pose_name or nil")
			end

			if joint.kind ~= nil
				and joint.kind ~= "part_motor"
				and joint.kind ~= "bone"
				and joint.kind ~= "animation_constraint" then
				add_error(errors, path .. ".kind", "must be part_motor, bone, or animation_constraint")
			end
		end
	end

	if root_count ~= 1 then
		add_error(errors, "config.joints", "must contain exactly one root pose")
	end

	for index, joint in ipairs(joints) do
		if is_table(joint) and joint.parent_pose ~= nil and joint.parent_pose ~= "" then
			if by_pose_name[joint.parent_pose] == nil then
				add_error(
					errors,
					string.format("config.joints[%d].parent_pose", index),
					"does not name another configured pose"
				)
			end
		end
	end

	-- Detect cycles deterministically by walking the ordered joint list. A
	-- parent must eventually terminate at the sole root.
	local visit = {}
	local function visit_pose(pose_name)
		if visit[pose_name] == 1 then
			return false
		elseif visit[pose_name] == 2 then
			return true
		end

		visit[pose_name] = 1
		local joint = by_pose_name[pose_name]
		if joint == nil or joint.parent_pose == nil or joint.parent_pose == "" then
			visit[pose_name] = 2
			return true
		end

		if not by_pose_name[joint.parent_pose] or not visit_pose(joint.parent_pose) then
			return false
		end

		visit[pose_name] = 2
		return true
	end

	for _, joint in ipairs(joints) do
		if is_table(joint) and is_nonempty_string(joint.pose_name) then
			if not visit_pose(joint.pose_name) then
				add_error(errors, "config.joints", "parent_pose hierarchy contains a cycle")
				break
			end
		end
	end

	return by_pose_name
end

local function validate_sample(sample, sample_index, joints, rig, errors)
	local path = string.format("config.poses[%d]", sample_index)
	if not is_table(sample) then
		add_error(errors, path, "must be a table")
		return
	end

	if not is_finite_number(sample.time) or sample.time < 0 then
		add_error(errors, path .. ".time", "must be a finite number >= 0")
	end
	if sample.name ~= nil and not is_nonempty_string(sample.name) then
		add_error(errors, path .. ".name", "must be a non-empty string when provided")
	end

	if not is_table(sample.joints) then
		add_error(errors, path .. ".joints", "must be a table")
		return
	end

	for _, joint in ipairs(joints) do
		if is_table(joint) and is_nonempty_string(joint.pose_name) then
			local value = sample.joints[joint.pose_name]
			if value == nil then
				add_error(
					errors,
					string.format("%s.joints.%s", path, joint.pose_name),
					"is required; provide a CFrame for every configured pose"
				)
			elseif not is_finite_cframe(value) then
				add_error(
					errors,
					string.format("%s.joints.%s", path, joint.pose_name),
					"must be a finite CFrame"
				)
			end
		end
	end

	-- Reject a configured target that is absent from this exact rig. The rig is
	-- supplied by the caller; no Workspace search or automatic remapping occurs.
	if is_instance(rig) and rig:IsA("Model") then
		for joint_index, joint in ipairs(joints) do
			if is_table(joint) and is_nonempty_string(joint.pose_name) then
				local target = get_target(rig, joint)
				if target == nil then
					add_error(
						errors,
						string.format("config.joints[%d]", joint_index),
						"instance_name was not found below the supplied rig"
					)
				elseif not target:IsA("BasePart") then
					add_error(
						errors,
						string.format("config.joints[%d].instance_name", joint_index),
						"must resolve to a BasePart for the KeyframeSequence/Pose route"
					)
				end
				if joint.kind == "bone" or joint.kind == "animation_constraint" then
					add_error(
						errors,
						string.format("config.joints[%d].kind", joint_index),
						"Bone and AnimationConstraint targets require the native curve/import adapter"
					)
				end
			end
		end
	end
end

function RobloxClipTemplate.validate_config(rig, config)
	local errors = {}

	if not is_instance(rig) or not rig:IsA("Model") then
		add_error(errors, "rig", "must be an explicitly supplied Model instance")
	end

	if not is_table(config) then
		add_error(errors, "config", "must be a table")
		return false, errors
	end

	local route = config.route or "keyframe_sequence"
	if route ~= "keyframe_sequence" then
		add_error(
			errors,
			"config.route",
			"this template supports keyframe_sequence only; use a CurveAnimation or import adapter for " .. tostring(route)
		)
	end

	if config.target_kind ~= nil
		and config.target_kind ~= "part_motor"
		and config.target_kind ~= "bone"
		and config.target_kind ~= "animation_constraint" then
		add_error(errors, "config.target_kind", "must be part_motor, bone, or animation_constraint")
	elseif config.target_kind == "bone" or config.target_kind == "animation_constraint" then
		add_error(
			errors,
			"config.target_kind",
			"KeyframeSequence/Pose template does not claim Bone or AnimationConstraint playback; use the native curve/import route"
		)
	end

	if config.name ~= nil and not is_nonempty_string(config.name) then
		add_error(errors, "config.name", "must be a non-empty string when provided")
	end

	if not is_finite_number(config.fps) or config.fps <= 0 then
		add_error(errors, "config.fps", "must be a finite number > 0")
	end

	if config.looped ~= nil and type(config.looped) ~= "boolean" then
		add_error(errors, "config.looped", "must be boolean when provided")
	end

	if config.priority ~= nil
		and (typeof(config.priority) ~= "EnumItem"
			or not tostring(config.priority):match("^Enum%.AnimationPriority%.")) then
		add_error(errors, "config.priority", "must be an Enum.AnimationPriority item when provided")
	end

	local joints_valid = is_array(config.joints) and #config.joints > 0
	if not joints_valid then
		add_error(errors, "config.joints", "must be a non-empty array")
	end

	if not is_array(config.poses) or #config.poses == 0 then
		add_error(errors, "config.poses", "must be a non-empty array")
	elseif joints_valid then
		local previous_time = nil
		for index, sample in ipairs(config.poses) do
			if is_table(sample) and is_finite_number(sample.time) then
				if previous_time ~= nil and sample.time <= previous_time then
					add_error(errors, string.format("config.poses[%d].time", index), "must be strictly greater than the previous time")
				end
				previous_time = sample.time
			end
			validate_sample(sample, index, config.joints, rig, errors)
		end
	end

	if joints_valid then
		validate_joint_hierarchy(config.joints, errors)
	end

	if config.markers ~= nil then
		if not is_array(config.markers) then
			add_error(errors, "config.markers", "must be an array when provided")
		else
			for index, marker in ipairs(config.markers) do
				local path = string.format("config.markers[%d]", index)
				if not is_table(marker) then
					add_error(errors, path, "must be a table")
				else
					if not is_positive_integer(marker.keyframe)
						or not is_array(config.poses)
						or marker.keyframe > #config.poses then
						add_error(errors, path .. ".keyframe", "must reference an existing 1-based pose sample")
					end
					if not is_nonempty_string(marker.name) then
						add_error(errors, path .. ".name", "must be a non-empty string")
					end
					if marker.value ~= nil and type(marker.value) ~= "string" then
						add_error(errors, path .. ".value", "must be a string when provided")
					end
				end
			end
		end
	end

	return #errors == 0, errors
end

local function make_pose_tree(config, sample)
	local poses_by_name = {}
	for _, joint in ipairs(config.joints) do
		local pose = Instance.new("Pose")
		pose.Name = joint.pose_name
		pose.CFrame = sample.joints[joint.pose_name]
		poses_by_name[joint.pose_name] = pose
	end

	local roots = {}
	for _, joint in ipairs(config.joints) do
		local pose = poses_by_name[joint.pose_name]
		if joint.parent_pose == nil or joint.parent_pose == "" then
			roots[#roots + 1] = pose
		else
			poses_by_name[joint.parent_pose]:AddSubPose(pose)
		end
	end

	return roots
end

local function add_markers(keyframe, keyframe_index, markers)
	if markers == nil then
		return
	end

	for _, marker in ipairs(markers) do
		if marker.keyframe == keyframe_index then
			local keyframe_marker = Instance.new("KeyframeMarker")
			keyframe_marker.Name = marker.name
			if marker.value ~= nil then
				keyframe_marker.Value = marker.value
			end
			keyframe:AddMarker(keyframe_marker)
		end
	end
end

function RobloxClipTemplate.build_keyframe_sequence(rig, config)
	local valid, errors = RobloxClipTemplate.validate_config(rig, config)
	if not valid then
		return nil, {
			status = "INVALID_CONFIG",
			errors = errors,
		}
	end

	local sequence = Instance.new("KeyframeSequence")
	sequence.Name = config.name or "LocalClip"
	sequence.Loop = config.looped == true
	sequence.Priority = config.priority or Enum.AnimationPriority.Action

	for index, sample in ipairs(config.poses) do
		local keyframe = Instance.new("Keyframe")
		keyframe.Name = sample.name or string.format("Keyframe_%03d", index)
		keyframe.Time = sample.time

		local roots = make_pose_tree(config, sample)
		for _, root_pose in ipairs(roots) do
			keyframe:AddPose(root_pose)
		end
		add_markers(keyframe, index, config.markers)
		sequence:AddKeyframe(keyframe)
	end

	return sequence, {
		status = "BUILT_LOCAL_UNPARENTED",
		_owner = OWNER_TOKEN,
		sequence = sequence,
		scope = "LOCAL_ONLY",
		keyframe_count = #config.poses,
		fps = config.fps,
	}
end

function RobloxClipTemplate.register_local(sequence, options)
	options = options or {}
	if options.enabled ~= true then
		return {
			status = "NOT_REQUESTED",
			scope = "LOCAL_ONLY",
			note = "Set options.enabled = true only for an explicit disposable Studio preview probe.",
		}
	end
	if options.datamodel_type ~= "Edit"
		and options.datamodel_type ~= "Client"
		and options.datamodel_type ~= "Server" then
		return {
			status = "INVALID_INPUT",
			scope = "LOCAL_ONLY",
			error = "datamodel_type must be explicitly Edit, Client, or Server",
		}
	end
	if options.disposable ~= true then
		return {
			status = "INVALID_INPUT",
			scope = "LOCAL_ONLY",
			error = "options.disposable = true is required; this template will not register into an unspecified place",
		}
	end

	if not is_instance(sequence) or not sequence:IsA("KeyframeSequence") then
		return {
			status = "INVALID_INPUT",
			scope = "LOCAL_ONLY",
			error = "sequence must be a KeyframeSequence built by this route",
		}
	end

	local method_name = options.method or "RegisterAnimationClip"
	if method_name ~= "RegisterAnimationClip" and method_name ~= "RegisterActiveAnimationClip" then
		return {
			status = "INVALID_INPUT",
			scope = "LOCAL_ONLY",
			error = "method must be RegisterAnimationClip or RegisterActiveAnimationClip",
		}
	end

	local service_ok, provider_or_error = pcall(function()
		return game:GetService("AnimationClipProvider")
	end)
	if not service_ok or provider_or_error == nil then
		return {
			status = "CAPABILITY_UNAVAILABLE",
			scope = "LOCAL_ONLY",
			datamodel_type = options.datamodel_type,
			method = method_name,
			error = tostring(provider_or_error),
		}
	end

	local provider = provider_or_error
	local method = provider[method_name]
	if type(method) ~= "function" then
		return {
			status = "CAPABILITY_UNAVAILABLE",
			scope = "LOCAL_ONLY",
			datamodel_type = options.datamodel_type,
			method = method_name,
			error = "provider method is unavailable in this Studio context",
		}
	end

	local call_ok, returned_id = pcall(method, provider, sequence)
	if not call_ok then
		return {
			status = "REGISTER_FAILED",
			scope = "LOCAL_ONLY",
			datamodel_type = options.datamodel_type,
			method = method_name,
			error = tostring(returned_id),
		}
	end

	if returned_id == nil or tostring(returned_id) == "" then
		return {
			status = "REGISTER_FAILED",
			scope = "LOCAL_ONLY",
			datamodel_type = options.datamodel_type,
			method = method_name,
			error = "API returned no ContentId; no identifier was fabricated",
		}
	end

	return {
		status = "REGISTERED_LOCAL",
		_owner = OWNER_TOKEN,
		scope = "STUDIO_LOCAL_PREVIEW_ONLY",
		datamodel_type = options.datamodel_type,
		method = method_name,
		temporary_id = returned_id,
		note = "Use only in this disposable probe; this is not a cloud-published asset ID.",
	}
end

function RobloxClipTemplate.make_animation(registration)
	if type(registration) ~= "table"
		or registration._owner ~= OWNER_TOKEN
		or registration.status ~= "REGISTERED_LOCAL"
		or registration.temporary_id == nil then
		return nil, {
			status = "INVALID_REGISTRATION",
			error = "animation must be created from an actual REGISTERED_LOCAL result",
		}
	end

	local animation = Instance.new("Animation")
	local assignment_ok, assignment_error = pcall(function()
		animation.AnimationId = registration.temporary_id
	end)
	if not assignment_ok then
		animation:Destroy()
		return nil, {
			status = "INVALID_REGISTRATION",
			error = tostring(assignment_error),
		}
	end

	return animation, {
		status = "BUILT_LOCAL_ANIMATION_UNPARENTED",
		_owner = OWNER_TOKEN,
		animation = animation,
		scope = "LOCAL_ONLY",
	}
end

function RobloxClipTemplate.play_preview(animator, animation, options)
	options = options or {}
	if options.enabled ~= true
		or options.disposable ~= true
		or options.target ~= "explicit_disposable_animator" then
		return nil, {
			status = "NOT_REQUESTED",
			scope = "LOCAL_ONLY",
			note = "Playback requires explicit opt-in and an explicitly disposable Animator target.",
		}
	end

	if not is_instance(animator) or not animator:IsA("Animator") then
		return nil, {
			status = "INVALID_INPUT",
			scope = "LOCAL_ONLY",
			error = "animator must be an explicitly supplied Animator",
		}
	end
	if not is_instance(animation) or not animation:IsA("Animation") then
		return nil, {
			status = "INVALID_INPUT",
			scope = "LOCAL_ONLY",
			error = "animation must be an explicitly supplied Animation instance",
		}
	end

	local workspace_ok, in_workspace = pcall(function()
		return animator:IsDescendantOf(workspace)
	end)
	if not workspace_ok or not in_workspace then
		return nil, {
			status = "PREVIEW_TARGET_INVALID",
			scope = "LOCAL_ONLY",
			error = "Animator must be under Workspace for LoadAnimation; no target was changed",
		}
	end

	local load_ok, track_or_error = pcall(function()
		return animator:LoadAnimation(animation)
	end)
	if not load_ok then
		return nil, {
			status = "PLAYBACK_FAILED",
			scope = "LOCAL_ONLY",
			error = tostring(track_or_error),
		}
	end

	local track = track_or_error
	if options.priority ~= nil and typeof(options.priority) ~= "EnumItem" then
		pcall(function()
			track:Destroy()
		end)
		return nil, {
			status = "INVALID_INPUT",
			scope = "LOCAL_ONLY",
			error = "priority must be an Enum.AnimationPriority item when provided",
		}
	end
	if options.looped ~= nil and type(options.looped) ~= "boolean" then
		pcall(function()
			track:Destroy()
		end)
		return nil, {
			status = "INVALID_INPUT",
			scope = "LOCAL_ONLY",
			error = "looped must be boolean when provided",
		}
	end

	local fade_time = options.fade_time or 0
	local weight = options.weight or 1
	local speed = options.speed or 1
	if not is_finite_number(fade_time) or fade_time < 0
		or not is_finite_number(weight) or weight < 0
		or not is_finite_number(speed) or speed <= 0 then
		pcall(function()
			track:Destroy()
		end)
		return nil, {
			status = "INVALID_INPUT",
			scope = "LOCAL_ONLY",
			error = "fade_time/weight/speed must be finite and within playback bounds",
		}
	end

	local property_ok, property_error = pcall(function()
		if options.priority ~= nil then
			track.Priority = options.priority
		end
		if options.looped ~= nil then
			track.Looped = options.looped == true
		end
	end)
	if not property_ok then
		pcall(function()
			track:Destroy()
		end)
		return nil, {
			status = "PLAYBACK_FAILED",
			scope = "LOCAL_ONLY",
			error = tostring(property_error),
		}
	end

	local play_ok, play_error = pcall(function()
		track:Play(fade_time, weight, speed)
	end)
	if not play_ok then
		pcall(function()
			track:Destroy()
		end)
		return nil, {
			status = "PLAYBACK_FAILED",
			scope = "LOCAL_ONLY",
			error = tostring(play_error),
		}
	end

	return track, {
		status = "PLAYING_LOCAL_PREVIEW",
		_owner = OWNER_TOKEN,
		track = track,
		scope = "STUDIO_LOCAL_PREVIEW_ONLY",
	}
end

function RobloxClipTemplate.cleanup(state)
	if type(state) ~= "table" or state._owner ~= OWNER_TOKEN then
		return {
			status = "INVALID_OWNERSHIP",
			error = "cleanup accepts only a state returned by this template",
		}
	end

	local errors = {}
	if state.track ~= nil then
		local stop_ok, stop_error = pcall(function()
			state.track:Stop(0)
			state.track:Destroy()
		end)
		if not stop_ok then
			errors[#errors + 1] = tostring(stop_error)
		end
	end
	if state.animation ~= nil then
		local animation_ok, animation_error = pcall(function()
			state.animation:Destroy()
		end)
		if not animation_ok then
			errors[#errors + 1] = tostring(animation_error)
		end
	end
	if state.sequence ~= nil then
		local sequence_ok, sequence_error = pcall(function()
			state.sequence:Destroy()
		end)
		if not sequence_ok then
			errors[#errors + 1] = tostring(sequence_error)
		end
	end

	if #errors > 0 then
		return {
			status = "CLEANUP_PARTIAL",
			errors = errors,
		}
	end
	return { status = "CLEANED_LOCAL_OWNED_OBJECTS" }
end

return RobloxClipTemplate
