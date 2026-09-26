// SPDX-License-Identifier: GPL-2.0-only
/*
 * Fault Simulation Disk
 *
 * A Linux block-device simulator for reproducible storage fault testing.
 */

#define pr_fmt(fmt) KBUILD_MODNAME ": " fmt

#include <linux/bio.h>
#include <linux/blkdev.h>
#include <linux/debugfs.h>
#include <linux/highmem.h>
#include <linux/init.h>
#include <linux/jiffies.h>
#include <linux/module.h>
#include <linux/moduleparam.h>
#include <linux/random.h>
#include <linux/seq_file.h>
#include <linux/slab.h>
#include <linux/spinlock.h>
#include <linux/version.h>
#include <linux/vmalloc.h>
#include <linux/workqueue.h>

#define FSD_DRIVER_NAME "faultsimdisk"
#define FSD_DISK_NAME "faultsim0"
#define FSD_SECTOR_SIZE 512U
#define FSD_DEFAULT_SIZE_MB 64UL
#define FSD_MIN_SIZE_MB 8UL
#define FSD_MAX_SIZE_MB 1024UL
#define FSD_MAX_LATENCY_MS 5000U

struct fsd_stats {
	atomic64_t read_requests;
	atomic64_t write_requests;
	atomic64_t read_bytes;
	atomic64_t write_bytes;
	atomic64_t failed_reads;
	atomic64_t failed_writes;
	atomic64_t delayed_requests;
};

struct fsd_device {
	int major;
	struct gendisk *disk;
	u8 *data;
	size_t capacity_bytes;
	spinlock_t data_lock;
	struct workqueue_struct *io_wq;
	struct dentry *debugfs_dir;
	struct fsd_stats stats;
};

struct fsd_io_work {
	struct delayed_work work;
	struct bio *bio;
	bool fail;
};

static struct fsd_device fsd;

static unsigned long size_mb = FSD_DEFAULT_SIZE_MB;
module_param(size_mb, ulong, 0444);
MODULE_PARM_DESC(size_mb, "Device capacity in MiB (8-1024, default 64)");

static unsigned int latency_ms;
static unsigned int read_fail_pct;
static unsigned int write_fail_pct;

static int fsd_set_latency(const char *val, const struct kernel_param *kp)
{
	unsigned int parsed;
	int ret;

	ret = kstrtouint(val, 0, &parsed);
	if (ret)
		return ret;
	if (parsed > FSD_MAX_LATENCY_MS)
		return -ERANGE;

	*(unsigned int *)kp->arg = parsed;
	return 0;
}

static int fsd_set_percent(const char *val, const struct kernel_param *kp)
{
	unsigned int parsed;
	int ret;

	ret = kstrtouint(val, 0, &parsed);
	if (ret)
		return ret;
	if (parsed > 100)
		return -ERANGE;

	*(unsigned int *)kp->arg = parsed;
	return 0;
}

static const struct kernel_param_ops fsd_latency_ops = {
	.set = fsd_set_latency,
	.get = param_get_uint,
};

static const struct kernel_param_ops fsd_percent_ops = {
	.set = fsd_set_percent,
	.get = param_get_uint,
};

module_param_cb(latency_ms, &fsd_latency_ops, &latency_ms, 0644);
MODULE_PARM_DESC(latency_ms, "Completion latency added to each I/O in milliseconds (0-5000)");

module_param_cb(read_fail_pct, &fsd_percent_ops, &read_fail_pct, 0644);
MODULE_PARM_DESC(read_fail_pct, "Percentage of read requests completed with I/O error (0-100)");

module_param_cb(write_fail_pct, &fsd_percent_ops, &write_fail_pct, 0644);
MODULE_PARM_DESC(write_fail_pct, "Percentage of write requests completed with I/O error (0-100)");

static void fsd_account_submit(const struct bio *bio)
{
	switch (bio_op(bio)) {
	case REQ_OP_READ:
		atomic64_inc(&fsd.stats.read_requests);
		break;
	case REQ_OP_WRITE:
		atomic64_inc(&fsd.stats.write_requests);
		break;
	default:
		break;
	}
}

static void fsd_account_failure(const struct bio *bio)
{
	switch (bio_op(bio)) {
	case REQ_OP_READ:
		atomic64_inc(&fsd.stats.failed_reads);
		break;
	case REQ_OP_WRITE:
		atomic64_inc(&fsd.stats.failed_writes);
		break;
	default:
		break;
	}
}

static void fsd_account_success(const struct bio *bio)
{
	switch (bio_op(bio)) {
	case REQ_OP_READ:
		atomic64_add(bio->bi_iter.bi_size, &fsd.stats.read_bytes);
		break;
	case REQ_OP_WRITE:
		atomic64_add(bio->bi_iter.bi_size, &fsd.stats.write_bytes);
		break;
	default:
		break;
	}
}

static int fsd_stats_show(struct seq_file *m, void *unused)
{
	(void)unused;

	seq_printf(m, "read_requests %lld\n",
		   (long long)atomic64_read(&fsd.stats.read_requests));
	seq_printf(m, "write_requests %lld\n",
		   (long long)atomic64_read(&fsd.stats.write_requests));
	seq_printf(m, "read_bytes %lld\n",
		   (long long)atomic64_read(&fsd.stats.read_bytes));
	seq_printf(m, "write_bytes %lld\n",
		   (long long)atomic64_read(&fsd.stats.write_bytes));
	seq_printf(m, "failed_reads %lld\n",
		   (long long)atomic64_read(&fsd.stats.failed_reads));
	seq_printf(m, "failed_writes %lld\n",
		   (long long)atomic64_read(&fsd.stats.failed_writes));
	seq_printf(m, "delayed_requests %lld\n",
		   (long long)atomic64_read(&fsd.stats.delayed_requests));
	seq_printf(m, "latency_ms %u\n", READ_ONCE(latency_ms));
	seq_printf(m, "read_fail_pct %u\n", READ_ONCE(read_fail_pct));
	seq_printf(m, "write_fail_pct %u\n", READ_ONCE(write_fail_pct));

	return 0;
}
DEFINE_SHOW_ATTRIBUTE(fsd_stats);

static void fsd_debugfs_init(void)
{
	struct dentry *stats_file;

	fsd.debugfs_dir = debugfs_create_dir(FSD_DRIVER_NAME, NULL);
	if (IS_ERR(fsd.debugfs_dir)) {
		pr_warn("debugfs unavailable; runtime stats disabled\n");
		fsd.debugfs_dir = NULL;
		return;
	}

	stats_file = debugfs_create_file("stats", 0444, fsd.debugfs_dir,
					 NULL, &fsd_stats_fops);
	if (IS_ERR(stats_file)) {
		debugfs_remove_recursive(fsd.debugfs_dir);
		fsd.debugfs_dir = NULL;
		pr_warn("failed to create debugfs stats file\n");
	}
}

static bool fsd_bio_in_bounds(const struct bio *bio)
{
	u64 offset = (u64)bio->bi_iter.bi_sector << SECTOR_SHIFT;
	u64 length = bio->bi_iter.bi_size;

	return offset <= fsd.capacity_bytes &&
	       length <= fsd.capacity_bytes - offset;
}

static void fsd_copy_bio(struct bio *bio, bool write)
{
	struct bio_vec bvec;
	struct bvec_iter iter;
	size_t offset = (size_t)bio->bi_iter.bi_sector << SECTOR_SHIFT;

	bio_for_each_segment(bvec, bio, iter) {
		void *mapped = bvec_kmap_local(&bvec);
		unsigned long flags;

		spin_lock_irqsave(&fsd.data_lock, flags);
		if (write)
			memcpy(fsd.data + offset, mapped, bvec.bv_len);
		else
			memcpy(mapped, fsd.data + offset, bvec.bv_len);
		spin_unlock_irqrestore(&fsd.data_lock, flags);

		kunmap_local(mapped);
		offset += bvec.bv_len;
	}
}

static void fsd_zero_bio_range(struct bio *bio)
{
	size_t offset = (size_t)bio->bi_iter.bi_sector << SECTOR_SHIFT;
	unsigned long flags;

	spin_lock_irqsave(&fsd.data_lock, flags);
	memset(fsd.data + offset, 0, bio->bi_iter.bi_size);
	spin_unlock_irqrestore(&fsd.data_lock, flags);
}

static bool fsd_should_fail(const struct bio *bio)
{
	unsigned int failure_pct;

	switch (bio_op(bio)) {
	case REQ_OP_READ:
		failure_pct = READ_ONCE(read_fail_pct);
		break;
	case REQ_OP_WRITE:
		failure_pct = READ_ONCE(write_fail_pct);
		break;
	default:
		return false;
	}

	return failure_pct != 0 && get_random_u32_below(100) < failure_pct;
}

static void fsd_complete_bio(struct bio *bio, bool fail)
{
	if (fail) {
		fsd_account_failure(bio);
		bio->bi_status = BLK_STS_IOERR;
		bio_endio(bio);
		return;
	}

	switch (bio_op(bio)) {
	case REQ_OP_READ:
		fsd_copy_bio(bio, false);
		break;
	case REQ_OP_WRITE:
		fsd_copy_bio(bio, true);
		break;
	case REQ_OP_FLUSH:
		/* The in-memory backing store has no volatile write cache. */
		break;
	case REQ_OP_DISCARD:
	case REQ_OP_WRITE_ZEROES:
		fsd_zero_bio_range(bio);
		break;
	default:
		bio->bi_status = BLK_STS_NOTSUPP;
		bio_endio(bio);
		return;
	}

	fsd_account_success(bio);
	bio_endio(bio);
}

static void fsd_io_workfn(struct work_struct *work)
{
	struct fsd_io_work *io =
		container_of(to_delayed_work(work), struct fsd_io_work, work);

	fsd_complete_bio(io->bio, io->fail);
	kfree(io);
}

static void fsd_submit_bio(struct bio *bio)
{
	struct fsd_io_work *io;
	unsigned int delay_ms;

	fsd_account_submit(bio);

	if (!fsd_bio_in_bounds(bio)) {
		fsd_account_failure(bio);
		bio_io_error(bio);
		return;
	}

	delay_ms = READ_ONCE(latency_ms);
	if (delay_ms == 0) {
		fsd_complete_bio(bio, fsd_should_fail(bio));
		return;
	}

	io = kmalloc(sizeof(*io), GFP_ATOMIC);
	if (!io) {
		fsd_account_failure(bio);
		bio_io_error(bio);
		return;
	}

	io->bio = bio;
	io->fail = fsd_should_fail(bio);
	INIT_DELAYED_WORK(&io->work, fsd_io_workfn);

	if (!queue_delayed_work(fsd.io_wq, &io->work,
				msecs_to_jiffies(delay_ms))) {
		kfree(io);
		fsd_account_failure(bio);
		bio_io_error(bio);
		return;
	}

	atomic64_inc(&fsd.stats.delayed_requests);
}

static const struct block_device_operations fsd_fops = {
	.owner = THIS_MODULE,
	.submit_bio = fsd_submit_bio,
};

static struct gendisk *fsd_alloc_disk(void)
{
#if LINUX_VERSION_CODE >= KERNEL_VERSION(6, 9, 0)
	struct queue_limits limits = {
		.logical_block_size = FSD_SECTOR_SIZE,
		.physical_block_size = FSD_SECTOR_SIZE,
	};

	return blk_alloc_disk(&limits, NUMA_NO_NODE);
#else
	struct gendisk *disk = blk_alloc_disk(NUMA_NO_NODE);

	if (disk) {
		blk_queue_logical_block_size(disk->queue, FSD_SECTOR_SIZE);
		blk_queue_physical_block_size(disk->queue, FSD_SECTOR_SIZE);
	}

	return disk;
#endif
}

static int __init fsd_init(void)
{
	int ret;

	if (size_mb < FSD_MIN_SIZE_MB || size_mb > FSD_MAX_SIZE_MB) {
		pr_err("size_mb must be between %lu and %lu\n",
		       FSD_MIN_SIZE_MB, FSD_MAX_SIZE_MB);
		return -EINVAL;
	}

	fsd.capacity_bytes = (size_t)size_mb << 20;
	fsd.data = vzalloc(fsd.capacity_bytes);
	if (!fsd.data)
		return -ENOMEM;

	spin_lock_init(&fsd.data_lock);

	fsd.io_wq = alloc_workqueue(FSD_DRIVER_NAME "_io",
				    WQ_UNBOUND | WQ_MEM_RECLAIM, 0);
	if (!fsd.io_wq) {
		ret = -ENOMEM;
		goto err_free_data;
	}

	fsd.major = register_blkdev(0, FSD_DRIVER_NAME);
	if (fsd.major < 0) {
		ret = fsd.major;
		goto err_destroy_wq;
	}

	fsd.disk = fsd_alloc_disk();
	if (IS_ERR_OR_NULL(fsd.disk)) {
		ret = fsd.disk ? PTR_ERR(fsd.disk) : -ENOMEM;
		goto err_unregister_major;
	}

	fsd.disk->major = fsd.major;
	fsd.disk->first_minor = 0;
	fsd.disk->minors = 1;
	fsd.disk->fops = &fsd_fops;
	fsd.disk->private_data = &fsd;
	strscpy(fsd.disk->disk_name, FSD_DISK_NAME, DISK_NAME_LEN);
	set_capacity(fsd.disk, fsd.capacity_bytes >> SECTOR_SHIFT);

	ret = add_disk(fsd.disk);
	if (ret)
		goto err_put_disk;

	fsd_debugfs_init();

	pr_info("registered /dev/%s (%lu MiB)\n", FSD_DISK_NAME, size_mb);
	return 0;

err_put_disk:
	put_disk(fsd.disk);
err_unregister_major:
	unregister_blkdev(fsd.major, FSD_DRIVER_NAME);
err_destroy_wq:
	destroy_workqueue(fsd.io_wq);
err_free_data:
	vfree(fsd.data);
	fsd.data = NULL;
	return ret;
}

static void __exit fsd_exit(void)
{
	debugfs_remove_recursive(fsd.debugfs_dir);
	del_gendisk(fsd.disk);
	flush_workqueue(fsd.io_wq);
	destroy_workqueue(fsd.io_wq);
	put_disk(fsd.disk);
	unregister_blkdev(fsd.major, FSD_DRIVER_NAME);
	vfree(fsd.data);
	fsd.data = NULL;

	pr_info("unloaded\n");
}

module_init(fsd_init);
module_exit(fsd_exit);

MODULE_LICENSE("GPL");
MODULE_AUTHOR("Yan Yu");
MODULE_DESCRIPTION("Programmable Linux block-device simulator for storage fault testing");
