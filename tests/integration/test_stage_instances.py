import discord


async def test_stage_instance_lifecycle(env):
    stage = env.guild.create_stage_channel("Town Hall")
    await env.settle()

    cached = env.bot.get_channel(stage.id)
    instance = await cached.create_instance(topic="Weekly Q&A")
    await env.settle()
    assert instance.topic == "Weekly Q&A"

    fetched = await cached.fetch_instance()
    assert fetched.topic == "Weekly Q&A"

    await instance.edit(topic="Updated")
    await env.settle()
    assert (await cached.fetch_instance()).topic == "Updated"

    await instance.delete()
    await env.settle()
    try:
        await cached.fetch_instance()
    except discord.HTTPException:
        pass
    else:
        raise AssertionError("stage instance should be gone after delete")
